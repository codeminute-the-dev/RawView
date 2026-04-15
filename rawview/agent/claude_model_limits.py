"""Per-model max output tokens for Anthropic Claude (Messages API).

Caps follow https://platform.claude.com/docs/en/about-claude/models/overview
(synchronous Messages API). Update when Anthropic publishes new snapshot IDs.

Bedrock / Vertex style IDs are normalized (last path segment, ``anthropic.`` stripped)
before matching.
"""

from __future__ import annotations

# (prefix, max_output_tokens) — first matching prefix wins; list is most-specific first.
_CLAUDE_MODEL_PREFIX_MAX_OUTPUT: tuple[tuple[str, int], ...] = (
    # Claude 4.6 (latest)
    ("claude-opus-4-6", 128_000),
    ("claude-sonnet-4-6", 64_000),
    # Claude 4.5 / Haiku 4.5
    ("claude-haiku-4-5", 64_000),
    ("claude-opus-4-5", 64_000),
    ("claude-sonnet-4-5", 64_000),
    # Claude 4.1 / 4.0
    ("claude-opus-4-1", 32_000),
    ("claude-sonnet-4-20250514", 64_000),
    ("claude-opus-4-20250514", 32_000),
    ("claude-opus-4-", 32_000),
    ("claude-sonnet-4-", 64_000),
    ("claude-haiku-4-", 64_000),
    # Claude 3.x
    ("claude-3-5-haiku", 8192),
    ("claude-3-5-sonnet", 8192),
    ("claude-sonnet-3-5", 8192),
    ("claude-3-opus", 4096),
    ("claude-3-sonnet", 4096),
    ("claude-3-haiku", 4096),
    # Any other claude-* id
    ("claude-", 8192),
)


def _normalize_claude_model_id(model: str) -> str:
    m = (model or "").strip().lower()
    if not m:
        return ""
    if "/" in m:
        m = m.rsplit("/", maxsplit=1)[-1]
    if m.startswith("anthropic."):
        m = m[len("anthropic.") :]
    if "@" in m:
        m = m.split("@", maxsplit=1)[0]
    return m


def max_output_tokens_for_claude_model(model: str) -> int:
    """Return Anthropic's max ``max_tokens`` for this Claude model id (Messages API)."""
    m = _normalize_claude_model_id(model)
    if not m:
        return 8192
    for prefix, cap in _CLAUDE_MODEL_PREFIX_MAX_OUTPUT:
        if m.startswith(prefix):
            return cap
    return 8192
