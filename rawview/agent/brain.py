from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

import anthropic

from rawview.agent.memory import ConversationMemory
from rawview.agent.tools import anthropic_tool_list, run_tool
from rawview.ghidra.api import GhidraAPI

logger = logging.getLogger(__name__)

EmitFn = Callable[[str, dict[str, Any]], None]

# Short user phrases that should always map to Ghidra auto-analysis (model often replies in prose otherwise).
_ANALYZE_ALIASES = frozenset(
    {
        "analyze",
        "analyse",
        "analysis",
        "auto analyze",
        "auto-analyze",
        "autoanalysis",
        "run analysis",
        "run auto-analysis",
        "run auto analysis",
        "ghidra analyze",
        "auto analysis",
    }
)


def _expand_short_analyze_intent(text: str) -> str:
    t = text.strip().lower().rstrip(".!?")
    if not t:
        return text
    if t.startswith("please "):
        t = t.removeprefix("please ").strip()
    if t in _ANALYZE_ALIASES:
        return (
            "Run Ghidra auto-analysis on the currently loaded program now using the "
            "run_auto_analysis tool (it takes no arguments). After the tool returns, "
            "give a one-sentence confirmation."
        )
    return text


def _block_to_api_dict(block: object) -> dict[str, Any] | None:
    """Map SDK content block objects to Anthropic API-style dicts for message history."""
    btype = getattr(block, "type", None)
    if btype == "text":
        return {"type": "text", "text": getattr(block, "text", "")}
    if btype == "thinking":
        return {"type": "thinking", "thinking": getattr(block, "thinking", "")}
    if btype == "redacted_thinking":
        return {"type": "redacted_thinking", "data": getattr(block, "data", "")}
    if btype == "tool_use":
        tid = getattr(block, "id", "")
        name = getattr(block, "name", "")
        raw_inp = getattr(block, "input", None) or {}
        inp = dict(raw_inp) if isinstance(raw_inp, dict) else {}
        return {"type": "tool_use", "id": tid, "name": name, "input": inp}
    return None


class AgentBrain:
    """Anthropic tool loop with cooperative interrupt between turns."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        ghidra_api: GhidraAPI,
        memory: ConversationMemory,
        max_turns: int,
        on_navigate: Callable[[str], None],
        emit: EmitFn,
        extended_thinking: bool = False,
        thinking_budget_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._ghidra = ghidra_api
        self._memory = memory
        self._max_turns = max_turns
        self._on_navigate = on_navigate
        self._emit = emit
        self._extended_thinking = extended_thinking
        self._thinking_budget_tokens = thinking_budget_tokens
        self._temperature = float(temperature)
        self._interrupt = threading.Event()

    def interrupt(self) -> None:
        self._interrupt.set()

    def clear_interrupt(self) -> None:
        self._interrupt.clear()

    def run_user_prompt(self, text: str, *, goal: str | None = None) -> None:
        self.clear_interrupt()
        text = _expand_short_analyze_intent(text)
        self._memory.add_user(text)
        system = """
You are RawView, the in-app reverse-engineering agent. You act on a live Ghidra session through tools - not from memory of binaries you have not inspected.

## Safety and scope
- Stay focused on reverse engineering, Ghidra, and the loaded program. Help with malware analysis **only** as technical RE in a defensive or research context inside this tool.
- **Refuse** requests for instructions that enable serious real-world harm unrelated to legitimate RE - for example: weapons or explosives, terrorism, targeted harassment, non-consensual surveillance, or detailed guidance for committing crimes. Decline briefly and offer safe alternatives (e.g. general security concepts, or analysis confined to the binary at hand) when appropriate.
- Do not provide step-by-step instructions for self-harm; encourage seeking professional help instead.
- Normal RE tasks (unpacking, unpacking malware samples in Ghidra, exploit mitigation understanding, crypto in binaries) remain in scope when tied to analysis here.

## How you work
- Default to tools over speculation. If you lack facts (addresses, names, xrefs), fetch them; do not invent addresses or behavior.
- Work in tight loops: gather evidence → interpret → decide the next smallest tool step. Prefer incremental exploration over one giant assumption.
- After tool results, answer the user in clear prose: what you checked, what you found, and what it implies. Quote symbols or addresses from tool output when it helps.
- If the user’s target is ambiguous (multiple matches, unclear image base, vague “the crypto function”), ask one short clarifying question instead of guessing.

## Ghidra workflow (suggested order, adapt as needed)
- Orientation: list_functions, get_entry_points, get_imports/exports, get_strings as appropriate to map the surface.
- Drill-down: get_xrefs_to/from, get_disassembly, decompile_function, get_data_at, search_bytes, get_control_flow_graph.
- When you change the database (rename_function, rename_variable, set_comment, set_function_signature, create_struct), be deliberate and explain the rationale briefly to the user.

## Memory (two stores)
- **Conversation memory**: the `messages` you receive are the live chat transcript - prior **user** turns and **assistant** turns (assistant text plus tool calls; tool results arrive as following **user** messages per the API). Use them for continuity across sends. The UI may also show thinking that is **not** re-injected here to save context. When the user runs `/summarize`, older turns are replaced by a single bracketed Markdown summary - treat that block as authoritative shorthand for what was dropped.
- **Long-term agent memory** (`read_agent_memory` / `append_agent_memory`): a Markdown file on disk that persists across sessions. Use it for stable, reusable facts (binary identity, key function addresses you verified, architecture, analysis plan). Read it when the user refers to “last time,” prior goals, or anything that might already be recorded. Before appending, read if the file may be large or you might duplicate content. Never store secrets, credentials, API keys, or private personal data - summaries only.
- **Work dock** (`list_work_notes`, `read_work_markdown`, `append_work_markdown`): user-facing notes in the Work UI - prefer these for write-ups the human will edit alongside the session.

## Tools: how you must call them
You do **not** run Python, shell, or HTTP from here. Ghidra and the Work UI change only when **the host executes a tool** after you issue a proper tool call. Explaining what you “would” do in chat **does nothing** unless a matching tool actually runs.

### Put yourself in the right mode
1. You see a **tools** list in the request (each entry: tool `name`, human-readable `description`, machine `input_schema`). That list is the **only** callable function names - no hidden APIs.
2. Whenever you need **fresh data** from the binary (functions, strings, decompilation, xrefs, …), your next assistant turn should include a **`tool_use`** payload for that data. Guessing addresses or pasting fake JSON “results” in chat is a failure mode.
3. Each call is one object with **exactly two** fields you control: **`name`** (string, must match a tool `name` character-for-character) and **`input`** (a JSON **object** of arguments). This is **Anthropic’s shape**, not OpenAI’s: there is **no** `function` wrapper, **no** `arguments` string field - only `name` + `input` as a parsed object. If your habits say “arguments”, translate them into **`input`** here.

### What you emit (concretely)
- Your assistant message may contain normal **`text`** blocks (optional) plus one or more **`tool_use`** blocks. Only **`tool_use`** triggers execution.
- For every `tool_use`: set **`name`** to the tool identifier (e.g. `list_functions`, never `ListFunctions` or `list-functions`). Set **`input`** to a flat JSON object whose keys are **exactly** the property names from `input_schema` (`address`, not `addr` or `Address`). Include every **required** key; optional keys may be omitted.
- For tools with no parameters, **`input` must still be `{}`** (empty object). **`null`**, omitting `input`, or `[]` is wrong.
- After the host runs tools, you receive a **`user`** message whose content includes **`tool_result`** blocks. Each `content` is a **string** (often JSON). Parse that string; that is the ground truth.

### Before you call - 5-second checklist
- Is this tool name spelled **exactly** as in the tools list?
- Does `input` include **every required** key for that schema?
- Are addresses **JSON strings** (quoted)? Are counts like `length` **JSON numbers** (unquoted)?
- For `search_bytes`, is `pattern` several **two-digit hex tokens separated by spaces**?
- If the next step needs a value from a prior tool, did you **wait** for that `tool_result` first?

### Examples (same logical `name` + `input` you must supply)
- List functions: `name` = `list_functions`, `input` = `{}`.
- Decompile: `name` = `decompile_function`, `input` = {\"address\": \"004012a0\"}.
- Disassembly with limit: `name` = `get_disassembly`, `input` = {\"address\": \"004012a0\", \"length\": 48}.
- You may combine independent calls in **one** assistant message (e.g. `get_imports` + `get_entry_points`, each its own `tool_use` block).

### Frequent mistakes (avoid these)
- Answering the user with a long analysis **without** having issued the `tool_use` that would have produced the underlying facts.
- Putting the JSON arguments only inside a Markdown **code fence** in `text` - the runtime does **not** scrape code fences as tools.
- Using keys your intuition likes (`addr`, `fn`, `file`) instead of the schema’s keys (`address`, `path`, …).
- Passing `length` or `max_chars` as quoted strings - use numbers.
- Calling `run_auto_analysis` with invented keys - its `input` is always `{}`.

### After tools run
- Read **`tool_result`** content from the latest user message. You may add brief `text` in the same turn as tools, but **do not** pretend you already have tool output before it appears.

### Tools with no parameters (always pass `input`: `{}`)
- **`run_auto_analysis`**: Re-run auto-analysis on the program already open in Ghidra.
- **`list_functions`**: List defined functions and entry addresses.
- **`get_strings`**: List defined string literals and addresses.
- **`get_imports`**: List imported APIs/libraries.
- **`get_exports`**: Export-like symbols for this image (may be simplified).
- **`get_entry_points`**: Program entry symbols.
- **`list_work_notes`**: List Markdown files in the Work dock folder.

### Tools with parameters (name, purpose, `input` keys)
- **`open_file`**: Import a file from disk and run full analysis. `input`: `path` (string, absolute path to the binary).
- **`decompile_function`**: Decompiler output for one function. `input`: `address` (string, function entry).
- **`get_disassembly`**: Linear instructions from an address. `input`: `address` (string); optional `length` (integer, max instructions, default if omitted).
- **`navigate_to`**: Move the UI cursor/listing to an address. `input`: `address` (string).
- **`get_xrefs_to`**: References pointing **to** an address. `input`: `address` (string).
- **`get_xrefs_from`**: References going **out from** an address. `input`: `address` (string).
- **`rename_function`**: Persist a new function name. `input`: `address` (string), `new_name` (string).
- **`rename_variable`**: Rename a decompiler local. `input`: `function_address`, `old_name`, `new_name` (strings).
- **`set_comment`**: EOL comment in the database. `input`: `address` (string), `text` (string).
- **`search_bytes`**: First match of a fixed byte pattern from image min address. `input`: `pattern` (string): exact **space-separated** hex pairs only, e.g. `48 89 E5` - **no** wildcards.
- **`get_data_at`**: What Ghidra has at an address (data vs code). `input`: `address` (string).
- **`create_struct`**: Apply/create struct layout text at an address. `input`: `address`, `struct_definition` (strings); may be unsupported in some builds - check result JSON.
- **`set_function_signature`**: Set C-like prototype. `input`: `address`, `signature` (strings); may be unsupported - check result JSON.
- **`get_control_flow_graph`**: CFG metadata for a function. `input`: `address` (string).
- **`read_work_markdown`**: Read one Work-dock note. `input`: `filename` and/or `note` (string); optional `max_chars` (integer).
- **`append_work_markdown`**: Append to a Work-dock note. `input`: `markdown` (string, required); optional `tab_title` (string).
- **`read_agent_memory`**: Read persistent agent memory file. `input`: optional `max_chars` (integer) only; `{}` is valid.
- **`append_agent_memory`**: Append durable session facts to persistent memory. `input`: `markdown` (string, required).
- **`user_tip`**: Short UI tip for the user. `input`: `message` (string, required); use sparingly.

### Policy reminders
- **`open_file`**: new path on disk + full auto-analysis - not for “refresh the listing” of an already loaded program.
- **`run_auto_analysis`**: only the loaded program; if the user asks to analyze/re-analyze you **must** call this or `open_file`, never only describe doing so.
- **`navigate_to`**: UI only; does not change analysis.
- **`user_tip`**: rare UX hints - not where normal analysis belongs.

## Communication
- Keep tool arguments minimal and valid per each tool’s schema; when unsure, read the tool’s `description` and `input_schema` in the tool list.
- State uncertainty and alternatives when decompilation or types are wrong or incomplete - that is normal in RE.
- If a tool returns an error JSON, acknowledge it and recover (fix args, try another path, or ask the user).
""".strip()
        if goal:
            system += f"\nPinned goal: {goal}"

        tools = anthropic_tool_list(self._on_navigate)

        for _ in range(self._max_turns):
            if self._interrupt.is_set():
                self._emit("agent_stopped", {"reason": "interrupt"})
                return

            base_kwargs: dict[str, Any] = {
                "model": self._model,
                "system": system,
                "messages": self._memory.for_api(),
                "tools": tools,
                "temperature": self._temperature,
            }
            msg = None
            try:
                if self._extended_thinking:
                    budget = int(self._thinking_budget_tokens)
                    base_kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
                    base_kwargs["max_tokens"] = max(8192, budget + 2048)
                else:
                    base_kwargs["max_tokens"] = 8192
                msg = self._client.messages.create(**base_kwargs)
            except TypeError:
                logger.warning("messages.create rejected thinking kwargs; retrying without thinking")
                base_kwargs.pop("thinking", None)
                base_kwargs["max_tokens"] = 8192
                try:
                    msg = self._client.messages.create(**base_kwargs)
                except Exception as e:
                    logger.exception("Anthropic request failed")
                    self._emit("agent_error", {"message": str(e)})
                    return
            except Exception as e:
                if self._extended_thinking and "thinking" in base_kwargs:
                    logger.warning("Extended thinking failed (%s); retrying without it", e)
                    base_retry = {k: v for k, v in base_kwargs.items() if k != "thinking"}
                    base_retry["max_tokens"] = 8192
                    try:
                        msg = self._client.messages.create(**base_retry)
                    except Exception as e2:
                        logger.exception("Anthropic request failed")
                        self._emit("agent_error", {"message": str(e2)})
                        return
                else:
                    logger.exception("Anthropic request failed")
                    self._emit("agent_error", {"message": str(e)})
                    return

            assert msg is not None
            blocks_out: list[dict[str, Any]] = []
            tool_result_blocks: list[dict[str, Any]] = []

            for block in msg.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    t = getattr(block, "text", "")
                    self._emit("assistant_text", {"text": t})
                    bd = _block_to_api_dict(block)
                    if bd:
                        blocks_out.append(bd)
                elif btype == "thinking":
                    t = getattr(block, "thinking", "") or ""
                    self._emit("assistant_thinking", {"text": t})
                    # Do not persist thinking in rolling memory: saves tokens and avoids replay constraints;
                    # the UI stream still shows it.
                elif btype == "redacted_thinking":
                    self._emit("assistant_thinking", {"text": "[redacted thinking block]"})
                elif btype == "tool_use":
                    tid = getattr(block, "id", "")
                    name = getattr(block, "name", "")
                    raw_inp = getattr(block, "input", None) or {}
                    inp = dict(raw_inp) if isinstance(raw_inp, dict) else {}
                    self._emit("tool_call", {"id": tid, "name": name, "input": inp})
                    if self._interrupt.is_set():
                        result = json.dumps({"error": "interrupted_before_tool"})
                    else:
                        try:
                            result = run_tool(name, inp, self._ghidra, self._on_navigate, self._emit)
                        except Exception as e:
                            logger.exception("Tool %s failed", name)
                            result = json.dumps({"error": str(e)})
                    preview = result if len(result) < 4000 else result[:4000] + "..."
                    self._emit("tool_result", {"id": tid, "name": name, "preview": preview})
                    blocks_out.append({"type": "tool_use", "id": tid, "name": name, "input": inp})
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": result,
                        }
                    )

            if blocks_out:
                self._memory.add_assistant_blocks(blocks_out)

            if msg.stop_reason == "tool_use" and tool_result_blocks:
                self._memory.add_tool_results(tool_result_blocks)
                continue

            self._emit("agent_done", {"stop_reason": msg.stop_reason})
            return

        self._emit("agent_stopped", {"reason": "max_turns"})
