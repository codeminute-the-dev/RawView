"""Shared Anthropic request pacing: throttle between calls and backoff on rate limits."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import anthropic

logger = logging.getLogger(__name__)

AGENT_API_THROTTLE_SEC = 5.0
# After a 429, sleep this long before retrying the same request (cooperative with Stop).
AGENT_RATE_LIMIT_COOLDOWN_SEC = 300.0  # 5 minutes

NoticeEmit = Callable[[str, dict[str, Any]], None] | None
ShouldAbort = Callable[[], bool] | None


class AnthropicBackoffInterrupted(Exception):
    """Cooperative stop (e.g. user pressed Stop) during throttle or rate-limit wait."""


def _sleep_unless_abort(total_sec: float, should_abort: ShouldAbort) -> None:
    if total_sec <= 0:
        return
    if should_abort is None:
        time.sleep(total_sec)
        return
    deadline = time.monotonic() + total_sec
    while time.monotonic() < deadline:
        if should_abort():
            raise AnthropicBackoffInterrupted()
        chunk = min(0.25, deadline - time.monotonic())
        if chunk > 0:
            time.sleep(chunk)


def _format_wait_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    if total < 60:
        return f"{total} second" + ("" if total == 1 else "s")
    m, s = divmod(total, 60)
    parts: list[str] = []
    if m:
        parts.append(f"{m} minute" + ("" if m == 1 else "s"))
    if s:
        parts.append(f"{s} second" + ("" if s == 1 else "s"))
    return " ".join(parts) if parts else "0 seconds"


def _rate_limit_notice_message() -> str:
    return (
        "Anthropic rate limit hit. Waiting "
        f"{_format_wait_duration(AGENT_RATE_LIMIT_COOLDOWN_SEC)}, "
        "then retrying the same request."
    )


def is_anthropic_rate_limit(exc: BaseException) -> bool:
    if exc.__class__.__name__ == "RateLimitError":
        return True
    if getattr(exc, "status_code", None) == 429:
        return True
    return False


def messages_create_with_backoff(
    client: anthropic.Anthropic,
    emit: NoticeEmit,
    params: dict[str, Any],
    *,
    should_abort: ShouldAbort = None,
) -> Any:
    """Sleep before each attempt; on 429 emit optional notice, wait cooldown, retry."""
    skip_throttle = False
    while True:
        if not skip_throttle:
            _sleep_unless_abort(AGENT_API_THROTTLE_SEC, should_abort)
        skip_throttle = False
        if should_abort is not None and should_abort():
            raise AnthropicBackoffInterrupted()
        try:
            return client.messages.create(**params)
        except Exception as e:
            if is_anthropic_rate_limit(e):
                logger.warning("Anthropic rate limit (create), backing off: %s", e)
                if emit is not None:
                    emit("agent_notice", {"message": _rate_limit_notice_message()})
                _sleep_unless_abort(AGENT_RATE_LIMIT_COOLDOWN_SEC, should_abort)
                skip_throttle = True
                continue
            raise


def messages_stream_with_backoff(
    client: anthropic.Anthropic,
    emit: NoticeEmit,
    params: dict[str, Any],
    *,
    should_abort: ShouldAbort = None,
):
    """Return ``client.messages.stream(**params)`` after throttle; retry construction on 429."""
    skip_throttle = False
    while True:
        if not skip_throttle:
            _sleep_unless_abort(AGENT_API_THROTTLE_SEC, should_abort)
        skip_throttle = False
        if should_abort is not None and should_abort():
            raise AnthropicBackoffInterrupted()
        try:
            return client.messages.stream(**params)
        except Exception as e:
            if is_anthropic_rate_limit(e):
                logger.warning("Anthropic rate limit (stream), backing off: %s", e)
                if emit is not None:
                    emit("agent_notice", {"message": _rate_limit_notice_message()})
                _sleep_unless_abort(AGENT_RATE_LIMIT_COOLDOWN_SEC, should_abort)
                skip_throttle = True
                continue
            raise
