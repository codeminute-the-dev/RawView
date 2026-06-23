"""Discord Rich Presence for RawView.

Silently disabled when pypresence is not installed or Discord is not running.
Requires DISCORD_CLIENT_ID to be set (create a Discord application at
https://discord.com/developers/applications to get one).
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

try:
    from pypresence import Presence as _Presence
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class DiscordRichPresence:
    """Thread-safe Discord Rich Presence manager. All methods are non-blocking."""

    def __init__(self, client_id: str) -> None:
        self._client_id = client_id.strip()
        self._rpc: object | None = None
        self._lock = threading.Lock()
        self._start_time = int(time.time())
        self._program: str | None = None
        # Discord rate-limits updates to ~1 per 15s. Track last update time.
        self._last_update: float = 0.0

    def connect(self) -> None:
        """Connect to Discord in a background thread (no-op if client ID is empty)."""
        if not _AVAILABLE or not self._client_id:
            return
        threading.Thread(target=self._connect_bg, name="rawview-discord-connect", daemon=True).start()

    def _connect_bg(self) -> None:
        with self._lock:
            try:
                rpc = _Presence(self._client_id)
                rpc.connect()
                self._rpc = rpc
                self._push_update()
                logger.info("Discord Rich Presence connected (client_id=%s)", self._client_id)
            except Exception as exc:
                logger.debug("Discord Rich Presence unavailable: %s", exc)
                self._rpc = None

    def set_program(self, name: str | None) -> None:
        """Called when the loaded binary changes. Non-blocking."""
        self._program = name or None
        threading.Thread(target=self._update_bg, name="rawview-discord-update", daemon=True).start()

    def _update_bg(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now - self._last_update < 15.0:
                # Respect Discord's rate limit; the next natural update (e.g. from a
                # subsequent open) will carry the latest state.
                return
            self._push_update()

    def _push_update(self) -> None:
        """Must be called with self._lock held."""
        if self._rpc is None:
            return
        try:
            if self._program:
                self._rpc.update(  # type: ignore[union-attr]
                    details=f"Analyzing: {self._program}",
                    state="Reverse Engineering",
                    start=self._start_time,
                    large_image="rawview",
                    large_text="RawView",
                )
            else:
                self._rpc.update(  # type: ignore[union-attr]
                    details="RawView",
                    state="Idle",
                    start=self._start_time,
                    large_image="rawview",
                    large_text="RawView",
                )
            self._last_update = time.monotonic()
        except Exception as exc:
            logger.debug("Discord RPC update failed: %s", exc)
            self._rpc = None

    def close(self) -> None:
        """Disconnect from Discord. Called on app exit."""
        with self._lock:
            if self._rpc is not None:
                try:
                    self._rpc.close()  # type: ignore[union-attr]
                except Exception:
                    pass
                self._rpc = None
