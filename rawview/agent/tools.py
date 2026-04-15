from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rawview.agent.long_term_memory import append_agent_memory_text, agent_memory_path, read_agent_memory_text
from rawview.agent.web_search import perform_web_search
from rawview.ghidra.api import GhidraAPI
from rawview.qt_ui.work_dock import work_notes_dir

ToolHandler = Callable[[dict[str, Any], GhidraAPI, Callable[[str], None]], str]


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: ToolHandler

    def anthropic_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema,
        }


def _build_registry(
    on_navigate: Callable[[str], None],
    emit_fn: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, RegisteredTool]:
    def append_work_markdown(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        md = str(inp.get("markdown", ""))
        title = str(inp.get("tab_title", "")).strip()
        wd = work_notes_dir()
        if title:
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", title)[:60].strip("-") or "note"
            fname = f"{safe}.md"
        else:
            fname = "agent-notes.md"
        path = Path(wd) / fname
        wd.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        sep = "\n\n" if existing.strip() else ""
        path.write_text(existing + sep + md, encoding="utf-8")
        if emit_fn is not None:
            emit_fn("work_note_updated", {"path": str(path.resolve())})
        return json.dumps({"ok": True, "path": str(path.resolve())})

    def user_tip(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        msg = str(inp.get("message", ""))[:2000]
        if emit_fn is not None and msg.strip():
            emit_fn("user_tip", {"message": msg.strip()})
        return json.dumps({"ok": True})

    def list_work_notes(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        wd = work_notes_dir()
        wd.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        for f in sorted(wd.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            st = f.stat()
            rows.append({"filename": f.name, "bytes": st.st_size, "mtime": int(st.st_mtime)})
        return json.dumps({"notes": rows, "count": len(rows)})

    def read_work_markdown(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        wd = work_notes_dir()
        wd.mkdir(parents=True, exist_ok=True)
        key = str(inp.get("filename", "") or inp.get("note", "") or "").strip()
        if not key:
            return json.dumps({"error": "missing_filename"})
        base = Path(key.replace("\\", "/")).name
        if not base.endswith(".md"):
            base = f"{base}.md"
        path = (wd / base).resolve()
        try:
            path.relative_to(wd.resolve())
        except ValueError:
            return json.dumps({"error": "invalid_path"})
        if not path.is_file():
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(key).stem.lower())[:60].strip("-") or "note"
            alt = (wd / f"{slug}.md").resolve()
            if alt.is_file():
                path = alt
            else:
                return json.dumps({"error": "not_found", "tried": base})
        max_c = int(inp.get("max_chars", 60000) or 60000)
        max_c = max(1024, min(max_c, 200_000))
        text = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_c
        body = text[:max_c] if truncated else text
        return json.dumps(
            {
                "filename": path.name,
                "truncated": truncated,
                "markdown": body,
            }
        )

    def open_file(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        path = str(inp["path"])
        name = api.open_file(path)
        api.run_auto_analysis()
        if emit_fn is not None:
            emit_fn("ghidra_shell_refresh", {"program": name})
        return json.dumps({"program": name, "path": path})

    def run_auto(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        api.run_auto_analysis()
        if emit_fn is not None:
            emit_fn("ghidra_shell_refresh", {})
        return json.dumps({"status": "analysis_complete"})

    def list_functions(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        rows = api.list_functions()
        return json.dumps({"functions": rows, "count": len(rows)})

    def decompile_function(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        addr = str(inp["address"])
        text = api.decompile_function(addr)
        return json.dumps({"address": addr, "pseudocode": text})

    def get_disassembly(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        addr = str(inp["address"])
        length = int(inp.get("length", 64))
        text = api.get_disassembly(addr, length)
        return json.dumps({"address": addr, "listing": text})

    def navigate_to(inp: dict[str, Any], _api: GhidraAPI, nav: Callable[[str], None]) -> str:
        addr = str(inp["address"])
        nav(addr)
        return json.dumps({"navigated": addr})

    def get_strings(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        rows = api.get_strings()
        return json.dumps({"strings": rows, "count": len(rows)})

    def get_imports(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        rows = api.get_imports()
        return json.dumps({"imports": rows, "count": len(rows)})

    def get_exports(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        rows = api.get_exports()
        return json.dumps({"exports": rows, "count": len(rows)})

    def get_entry_points(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        rows = api.get_entry_points()
        return json.dumps({"entry_points": rows})

    def get_xrefs_to(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        addr = str(inp["address"])
        rows = api.get_xrefs_to(addr)
        return json.dumps({"address": addr, "xrefs": rows})

    def get_xrefs_from(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        addr = str(inp["address"])
        rows = api.get_xrefs_from(addr)
        return json.dumps({"address": addr, "xrefs": rows})

    def rename_function(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        res = api.rename_function(str(inp["address"]), str(inp["new_name"]))
        if emit_fn is not None:
            emit_fn("ghidra_shell_refresh", {})
        return json.dumps(res)

    def rename_variable(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        return json.dumps(
            api.rename_variable(str(inp["function_address"]), str(inp["old_name"]), str(inp["new_name"]))
        )

    def set_comment(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        res = api.set_comment(str(inp["address"]), str(inp["text"]))
        if emit_fn is not None:
            emit_fn("ghidra_shell_refresh", {})
        return json.dumps(res)

    def search_bytes(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        return json.dumps(api.search_bytes(str(inp["pattern"])))

    def get_data_at(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        return json.dumps(api.get_data_at(str(inp["address"])))

    def create_struct(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        return json.dumps(api.create_struct(str(inp["address"]), str(inp["struct_definition"])))

    def set_function_signature(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        return json.dumps(api.set_function_signature(str(inp["address"]), str(inp["signature"])))

    def get_control_flow_graph(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        return json.dumps(api.get_control_flow_graph(str(inp["address"])))

    def read_agent_memory(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        max_c = int(inp.get("max_chars", 32000) or 32000)
        max_c = max(256, min(max_c, 200_000))
        body, truncated, approx_b = read_agent_memory_text(max_chars=max_c)
        return json.dumps(
            {
                "path": str(agent_memory_path().resolve()),
                "markdown": body,
                "truncated": truncated,
                "approx_total_bytes": approx_b,
            }
        )

    def append_agent_memory(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        md = str(inp.get("markdown", ""))
        if not md.strip():
            return json.dumps({"error": "empty_markdown"})
        path = append_agent_memory_text(md)
        return json.dumps({"ok": True, "path": str(path.resolve())})

    def web_search(inp: dict[str, Any], api: GhidraAPI, _nav: Callable[[str], None]) -> str:
        q = str(inp.get("query", ""))
        max_r = int(inp.get("max_results", 6) or 6)
        fetch_ex = bool(inp.get("fetch_primary_excerpt", False))
        out = perform_web_search(q, max_results=max_r, fetch_primary_excerpt=fetch_ex)
        return json.dumps(out, ensure_ascii=False)

    def batch_run_tools(inp: dict[str, Any], api: GhidraAPI, nav: Callable[[str], None]) -> str:
        calls = inp.get("calls")
        if not isinstance(calls, list) or not calls:
            return json.dumps({"error": "calls_must_be_non_empty_array"})
        if len(calls) > 24:
            return json.dumps({"error": "max_24_calls_per_batch", "got": len(calls)})
        results: list[dict[str, Any]] = []
        for i, c in enumerate(calls):
            if not isinstance(c, dict):
                results.append({"index": i, "error": "each_call_must_be_object"})
                continue
            n = str(c.get("name", "")).strip()
            sub = c.get("input")
            if not isinstance(sub, dict):
                sub = {}
            if n == "batch_run_tools":
                results.append({"index": i, "error": "nested_batch_run_tools_not_allowed"})
                continue
            if not n:
                results.append({"index": i, "error": "missing_tool_name"})
                continue
            try:
                out = run_tool(n, sub, api, nav, emit_fn)
                results.append({"index": i, "name": n, "result": out})
            except Exception as e:
                results.append({"index": i, "name": n, "error": str(e)})
        return json.dumps({"ok": True, "count": len(calls), "results": results}, ensure_ascii=False)

    tools: list[RegisteredTool] = [
        RegisteredTool(
            name="open_file",
            description=(
                "Import a new executable/library into Ghidra from disk, make it the active program, then run "
                "full automatic analysis (analysis scripts, references, etc.). The main window File → Open path "
                "only imports until you run auto-analysis manually; this tool always analyzes after import. "
                "Use when the user supplies a path or wants to switch binaries. Do not use for re-analyzing an "
                "already loaded image (use run_auto_analysis)."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute file path to the binary (Windows: drive letter, escaped backslashes ok).",
                    }
                },
                "required": ["path"],
            },
            handler=open_file,
        ),
        RegisteredTool(
            name="run_auto_analysis",
            description=(
                "Re-run Ghidra’s automatic analysis pipeline on the **currently loaded** program only. "
                "Takes no arguments. Use after renaming segments, changing loader options, or when the user "
                "explicitly asks to (re)analyze or refresh analysis. open_file already runs analysis once after import."
            ),
            parameters_schema={
                "type": "object",
                "properties": {},
                "description": "No parameters.",
            },
            handler=run_auto,
        ),
        RegisteredTool(
            name="list_functions",
            description=(
                "Return every defined function: names, entry addresses, and basic metadata. Best first step "
                "after load to locate interesting code; pair with get_entry_points or get_imports to prioritize."
            ),
            parameters_schema={"type": "object", "properties": {}},
            handler=list_functions,
        ),
        RegisteredTool(
            name="decompile_function",
            description=(
                "High-level pseudocode for the function whose entry is at `address` (Decompiler view). "
                "Prefer after narrowing with xrefs or list_functions. Output can be wrong or incomplete - verify "
                "critical paths with get_disassembly."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Function entry symbol or hex address (e.g. FUN_00401000 or 00401000).",
                    },
                },
                "required": ["address"],
            },
            handler=decompile_function,
        ),
        RegisteredTool(
            name="get_disassembly",
            description=(
                "Linear listing of instructions starting at `address` for up to `length` instructions. "
                "Use for exact opcodes, branches, and when decompiler output is misleading."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Instruction or label address to start listing from.",
                    },
                    "length": {
                        "type": "integer",
                        "description": "Maximum number of instructions (default 64; cap 5000 - keep small when possible).",
                    },
                },
                "required": ["address"],
            },
            handler=get_disassembly,
        ),
        RegisteredTool(
            name="navigate_to",
            description=(
                "Scrolls RawView/Ghidra UI focus to `address` so the user sees the same location you are discussing. "
                "Does not change analysis data - purely for coordination."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Address or symbol to jump the UI to."},
                },
                "required": ["address"],
            },
            handler=navigate_to,
        ),
        RegisteredTool(
            name="get_strings",
            description=(
                "All defined string literals (value + address). Fast way to find protocols, file paths, "
                "error messages, and hard-coded keys before deeper analysis."
            ),
            parameters_schema={"type": "object", "properties": {}},
            handler=get_strings,
        ),
        RegisteredTool(
            name="get_imports",
            description=(
                "Dynamic/static import table: external DLLs/APIs used by the binary. Use early to spot "
                "crypto, network, process, or file APIs."
            ),
            parameters_schema={"type": "object", "properties": {}},
            handler=get_imports,
        ),
        RegisteredTool(
            name="get_exports",
            description=(
                "Export-like symbols exposed by this image (implementation may be simplified/MVP). "
                "Useful for libraries and drivers; cross-check with list_functions."
            ),
            parameters_schema={"type": "object", "properties": {}},
            handler=get_exports,
        ),
        RegisteredTool(
            name="get_entry_points",
            description=(
                "Declared entry points (e.g. main image entry). Start here for execution flow when you need "
                "the first code that runs after the loader."
            ),
            parameters_schema={"type": "object", "properties": {}},
            handler=get_entry_points,
        ),
        RegisteredTool(
            name="get_xrefs_to",
            description=(
                "Every code/data reference **to** `address` (who calls or reads this). Essential for finding "
                "callers of a string, thunk, or API stub."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Target address or symbol that others refer to.",
                    },
                },
                "required": ["address"],
            },
            handler=get_xrefs_to,
        ),
        RegisteredTool(
            name="get_xrefs_from",
            description=(
                "References **from** `address` outward (calls, loads, jumps). Use inside a function to map "
                "its callees and data dependencies."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Instruction or data address to enumerate outgoing refs from.",
                    },
                },
                "required": ["address"],
            },
            handler=get_xrefs_from,
        ),
        RegisteredTool(
            name="rename_function",
            description=(
                "Persistently rename the function at `address` in the Ghidra database (affects listings and "
                "decompiler). Use descriptive reverse-engineered names; avoid renaming unless confident."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Entry address of the function to rename."},
                    "new_name": {
                        "type": "string",
                        "description": "Valid identifier-style name (letters, digits, underscore).",
                    },
                },
                "required": ["address", "new_name"],
            },
            handler=rename_function,
        ),
        RegisteredTool(
            name="rename_variable",
            description=(
                "Rename a stack/local variable inside a decompiled function. `old_name` must match the "
                "current decompiler name. May be unsupported for some functions - check tool JSON result."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "function_address": {"type": "string", "description": "Entry address of the containing function."},
                    "old_name": {"type": "string", "description": "Current variable name in decompiler output."},
                    "new_name": {"type": "string", "description": "New variable name."},
                },
                "required": ["function_address", "old_name", "new_name"],
            },
            handler=rename_variable,
        ),
        RegisteredTool(
            name="set_comment",
            description=(
                "Attach an end-of-line (EOL) comment at `address` in the database. Good for marking invariants, "
                "protocol fields, or TODOs visible in both listing and decompiler."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Instruction or data address."},
                    "text": {"type": "string", "description": "Short comment text (avoid secrets)."},
                },
                "required": ["address", "text"],
            },
            handler=set_comment,
        ),
        RegisteredTool(
            name="search_bytes",
            description=(
                "Binary search from the image minimum address for a literal byte pattern. Pattern is "
                'space-separated hex pairs, e.g. "48 89 E5" for x86-64 prologue. Returns hit addresses.'
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": 'Exact space-separated hex bytes (no wildcards), e.g. "48 89 E5".',
                    },
                },
                "required": ["pattern"],
            },
            handler=search_bytes,
        ),
        RegisteredTool(
            name="get_data_at",
            description=(
                "Inspect how Ghidra has typed the item at `address` (data, undefined, instruction). "
                "Use to verify structs, pointers, strings, or alignment before applying types."
            ),
            parameters_schema={
                "type": "object",
                "properties": {"address": {"type": "string", "description": "Any program address."}},
                "required": ["address"],
            },
            handler=get_data_at,
        ),
        RegisteredTool(
            name="create_struct",
            description=(
                "Lay down or apply a struct layout at `address` using `struct_definition` text (format depends "
                "on Ghidra bridge). May return not_implemented in MVP builds - use get_data_at if it fails."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Where to apply the struct."},
                    "struct_definition": {
                        "type": "string",
                        "description": "Struct definition string per Ghidra API expectations.",
                    },
                },
                "required": ["address", "struct_definition"],
            },
            handler=create_struct,
        ),
        RegisteredTool(
            name="set_function_signature",
            description=(
                "Set the function prototype (return type, name, args) to improve decompilation. May be "
                "not_implemented in MVP - check JSON response."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Function entry address."},
                    "signature": {
                        "type": "string",
                        "description": "C-like signature, e.g. int foo(char *a, size_t n);",
                    },
                },
                "required": ["address", "signature"],
            },
            handler=set_function_signature,
        ),
        RegisteredTool(
            name="get_control_flow_graph",
            description=(
                "Retrieve control-flow graph information for the function at `address` (shape, blocks, edges - "
                "exact schema depends on bridge; may be summary/placeholder JSON)."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Function entry address for CFG scope."},
                },
                "required": ["address"],
            },
            handler=get_control_flow_graph,
        ),
        RegisteredTool(
            name="list_work_notes",
            description=(
                "Enumerate Markdown files in the Work dock folder (mtime, size). Call before read_work_markdown "
                "or append_work_markdown when you need the correct filename or want to avoid duplicate notes."
            ),
            parameters_schema={"type": "object", "properties": {}},
            handler=list_work_notes,
        ),
        RegisteredTool(
            name="read_work_markdown",
            description=(
                "Load the contents of one Work-dock Markdown note by `filename` or `note` stem. Scoped to the "
                "work folder only (no arbitrary paths). Use max_chars to cap huge notes."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Basename like findings.md or a stem resolved to *.md in the work folder.",
                    },
                    "note": {"type": "string", "description": "Alias for filename if the latter is empty."},
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters returned (default 60000, hard max 200000).",
                    },
                },
            },
            handler=read_work_markdown,
        ),
        RegisteredTool(
            name="append_work_markdown",
            description=(
                "Append Markdown to a user-visible Work dock note (good for session write-ups the human edits). "
                "Creates the file if missing. `tab_title` slugifies into the filename; otherwise defaults to "
                "agent-notes.md. Prefer short structured sections over dumping full listings."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "markdown": {"type": "string", "description": "Markdown chunk to append (headings, bullets, links)."},
                    "tab_title": {
                        "type": "string",
                        "description": "Optional human-readable title used to derive the .md filename.",
                    },
                },
                "required": ["markdown"],
            },
            handler=append_work_markdown,
        ),
        RegisteredTool(
            name="read_agent_memory",
            description=(
                "Read RawView’s persistent **agent long-term memory** file (Markdown under the user data directory). "
                "Survives app restarts. Use when the user refers to past sessions, goals, or facts you may have "
                "stored earlier; read before large append_agent_memory updates so you do not duplicate or contradict prior notes."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters of the file to return (default 32000, max 200000).",
                    },
                },
            },
            handler=read_agent_memory,
        ),
        RegisteredTool(
            name="append_agent_memory",
            description=(
                "Append Markdown to the persistent agent memory file (same store as read_agent_memory). "
                "Use for durable, cross-session facts: binary goals, resolved identities of FUN_ labels, "
                "architecture, safe analysis checkpoints. **Do not** store passwords, API keys, tokens, or "
                "private personal data. Keep entries concise."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "markdown": {
                        "type": "string",
                        "description": "Markdown to append (e.g. bullet list of verified facts with dates).",
                    },
                },
                "required": ["markdown"],
            },
            handler=append_agent_memory,
        ),
        RegisteredTool(
            name="web_search",
            description=(
                "Search the public web for documentation, CVEs, vendor advisories, or general facts. "
                "Uses DuckDuckGo instant answers and related links (no API key). "
                "Verify critical claims against primary sources."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {
                        "type": "integer",
                        "description": "Max result rows to return (1–12). Default 6.",
                    },
                    "fetch_primary_excerpt": {
                        "type": "boolean",
                        "description": "If true, fetch the primary result page and include a short text excerpt (slower).",
                    },
                },
                "required": ["query"],
            },
            handler=web_search,
        ),
        RegisteredTool(
            name="batch_run_tools",
            description=(
                "Run multiple tools in one assistant turn to save tokens. Provide an array of {name, input} calls. "
                "Each call is independent (same rules as single tools). Max 24 calls; do not nest batch_run_tools."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "calls": {
                        "type": "array",
                        "description": "Ordered list of tool invocations.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "input": {"type": "object"},
                            },
                            "required": ["name", "input"],
                        },
                    }
                },
                "required": ["calls"],
            },
            handler=batch_run_tools,
        ),
        RegisteredTool(
            name="user_tip",
            description=(
                "Push a short, user-visible toast-style tip in the RawView UI. Reserve for rare UX guidance "
                "(where to click, what a panel means). Do not use for ordinary analysis text - put that in chat."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "One or two sentences; plain language; no markdown required.",
                    },
                },
                "required": ["message"],
            },
            handler=user_tip,
        ),
    ]
    return {t.name: t for t in tools}


def anthropic_tool_list(on_navigate: Callable[[str], None]) -> list[dict[str, Any]]:
    return [t.anthropic_schema() for t in _build_registry(on_navigate).values()]


def run_tool(
    name: str,
    arguments_json: str | Mapping[str, Any],
    api: GhidraAPI,
    on_navigate: Callable[[str], None],
    emit: Callable[[str, dict[str, Any]], None] | None = None,
) -> str:
    reg = _build_registry(on_navigate, emit)
    if name not in reg:
        return json.dumps({"error": f"unknown_tool:{name}"})
    if isinstance(arguments_json, str):
        inp = json.loads(arguments_json or "{}")
    else:
        inp = dict(arguments_json)
    return reg[name].handler(inp, api, on_navigate)
