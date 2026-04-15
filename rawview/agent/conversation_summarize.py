"""One-shot summarization of agent chat history for /summarize (no tools)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

import anthropic

from rawview.agent.anthropic_backoff import (
    AnthropicBackoffInterrupted,
    messages_create_with_backoff,
    messages_stream_with_backoff,
)

logger = logging.getLogger(__name__)

NoticeEmit = Callable[[str, dict[str, Any]], None] | None
ShouldAbort = Callable[[], bool] | None

_SUMMARY_SYSTEM = """You compress reverse-engineering chat transcripts for the RawView Ghidra agent.

The transcript uses sections === USER === and === ASSISTANT ===. Tool calls and JSON results appear inline.

Write a single Markdown document that will REPLACE the old transcript in the model context. Include:
1. **User goals**: what they asked, in order, briefly.
2. **Key findings**: verified addresses, function names, imports/strings called out, hypotheses that were confirmed or refuted.
3. **Actions taken**: notable renames, comments, files opened (names only).
4. **Open threads**: unanswered questions or next steps.

Rules:
- Drop verbatim long hex, full disassembly, and huge JSON; keep only what matters for continuing RE.
- Preserve exact addresses/symbols when they are load-bearing for follow-up.
- Be as short as clarity allows (typical target: under 2-3k words unless the source is tiny).
- Do not invent facts not present in the transcript."""


def flatten_messages_for_summary(
    messages: list[dict[str, Any]],
    *,
    max_transcript_chars: int = 280_000,
) -> str:
    """Turn API-style message list into plain text for the summarizer model."""
    parts: list[str] = []
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        parts.append(f"=== {str(role).upper()} ===")
        parts.append(_flatten_content(content))
        parts.append("")
    text = "\n".join(parts).strip()
    if len(text) <= max_transcript_chars:
        return text
    head = max_transcript_chars // 2
    tail = max_transcript_chars - head - 120
    return (
        text[:head]
        + "\n\n... [middle of transcript truncated for summarizer input] ...\n\n"
        + text[-tail:]
    )


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        lines: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                lines.append(str(block.get("text", "")))
            elif btype in ("thinking", "redacted_thinking"):
                lines.append("[thinking block omitted]")
            elif btype == "tool_use":
                name = block.get("name", "")
                inp = block.get("input", {})
                try:
                    inp_s = json.dumps(inp, ensure_ascii=False)[:4000]
                except (TypeError, ValueError):
                    inp_s = str(inp)[:4000]
                lines.append(f"Tool use: {name} {inp_s}")
            elif btype == "tool_result":
                body = str(block.get("content", ""))
                cap = 2500
                if len(body) > cap:
                    body = body[:cap] + "…(truncated)"
                lines.append(f"Tool result: {body}")
            else:
                lines.append(str(block)[:2000])
        return "\n".join(lines)
    return str(content)[:50_000]


def _text_from_message(msg: Any) -> str:
    out: list[str] = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            out.append(getattr(block, "text", "") or "")
    return "\n".join(out).strip()


def summarize_conversation_transcript(
    *,
    api_key: str,
    model: str,
    transcript: str,
    temperature: float = 0.2,
    emit: NoticeEmit = None,
    should_abort: ShouldAbort = None,
) -> str:
    if not transcript.strip():
        raise ValueError("empty_transcript")
    client = anthropic.Anthropic(api_key=api_key)
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": 8192,
        "temperature": float(temperature),
        "system": _SUMMARY_SYSTEM,
        "messages": [{"role": "user", "content": transcript}],
    }

    if hasattr(client.messages, "stream"):
        try:
            stream_began = False
            with messages_stream_with_backoff(client, emit, params, should_abort=should_abort) as stream:
                if emit is not None:
                    emit("assistant_stream_begin", {"source": "summarize"})
                stream_began = True
                try:
                    text_stream = getattr(stream, "text_stream", None)
                    if text_stream is None:
                        raise AttributeError("no text_stream")
                    for text in text_stream:
                        if should_abort is not None and should_abort():
                            raise AnthropicBackoffInterrupted()
                        if emit is not None:
                            emit("assistant_text_delta", {"text": text, "source": "summarize"})
                    msg = stream.get_final_message()
                finally:
                    if emit is not None and stream_began:
                        emit("assistant_stream_end", {"source": "summarize"})
            text = _text_from_message(msg)
            if not text:
                raise RuntimeError("summarizer_returned_no_text")
            if emit is not None:
                emit("assistant_stream_commit", {"text": text, "source": "summarize"})
            return text
        except AnthropicBackoffInterrupted:
            raise
        except Exception as e:
            logger.warning("/summarize streaming failed (%s); falling back to non-streaming", e)

    msg = messages_create_with_backoff(client, emit, params, should_abort=should_abort)
    text = _text_from_message(msg)
    if not text:
        raise RuntimeError("summarizer_returned_no_text")
    if emit is not None:
        emit("assistant_stream_commit", {"text": text, "source": "summarize"})
    return text
