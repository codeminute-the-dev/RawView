"""Persistent Markdown scratchpad for the agent (survives restarts; lives under user_data_dir)."""

from __future__ import annotations

from pathlib import Path

from rawview.config import user_data_dir

_AGENT_MEMORY_NAME = "agent_long_term_memory.md"
_DEFAULT_HEADER = (
    "<!-- RawView agent long-term memory. The model may read/append this file. "
    "Do not store secrets, credentials, or private personal data. -->\n\n"
)
_MAX_APPEND_CHARS = 120_000


def agent_memory_path() -> Path:
    return user_data_dir() / _AGENT_MEMORY_NAME


def read_agent_memory_text(*, max_chars: int) -> tuple[str, bool, int]:
    """
    Return (body, truncated, total_byte_length_approximately).
    """
    path = agent_memory_path()
    if not path.is_file():
        return "", False, 0
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    total = len(text.encode("utf-8", errors="replace"))
    if len(text) <= max_chars:
        return text, False, total
    return text[:max_chars], True, total


def append_agent_memory_text(markdown: str) -> Path:
    chunk = markdown.strip()
    if len(chunk) > _MAX_APPEND_CHARS:
        chunk = chunk[:_MAX_APPEND_CHARS] + "\n\n…(truncated to max append size)"
    path = agent_memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(_DEFAULT_HEADER, encoding="utf-8")
    existing = path.read_text(encoding="utf-8", errors="replace")
    sep = "\n\n" if existing.strip() else ""
    path.write_text(existing + sep + chunk + "\n", encoding="utf-8")
    return path
