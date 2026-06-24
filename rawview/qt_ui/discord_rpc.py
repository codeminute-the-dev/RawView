"""Discord Rich Presence for RawView.

Silently disabled when pypresence is not installed or Discord is not running.
The DISCORD_CLIENT_ID env var can override the built-in app key.
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

_HEARTBEAT_INTERVAL = 15.0


class DiscordRichPresence:
    """Thread-safe Discord Rich Presence manager. All methods are non-blocking."""

    def __init__(self, client_id: str) -> None:
        self._client_id = client_id.strip()
        self._rpc: object | None = None
        self._lock = threading.Lock()
        self._start_time: float = 0.0
        self._program: str | None = None
        self._stopped = threading.Event()

    def connect(self) -> None:
        if not _AVAILABLE or not self._client_id:
            return
        threading.Thread(target=self._connect_bg, name="rawview-discord-connect", daemon=True).start()

    def _connect_bg(self) -> None:
        with self._lock:
            try:
                rpc = _Presence(self._client_id)
                rpc.connect()
                self._rpc = rpc
                self._start_time = time.time()
                self._push_update()
                logger.info("Discord Rich Presence connected (client_id=%s)", self._client_id)
            except Exception as exc:
                logger.debug("Discord Rich Presence unavailable: %s", exc)
                self._rpc = None
                return
        self._start_heartbeat()

    def _start_heartbeat(self) -> None:
        t = threading.Thread(target=self._heartbeat_bg, name="rawview-discord-heartbeat", daemon=True)
        t.start()

    def _heartbeat_bg(self) -> None:
        while not self._stopped.is_set():
            if self._stopped.wait(_HEARTBEAT_INTERVAL):
                break
            with self._lock:
                if self._rpc is not None:
                    try:
                        self._push_update()
                    except Exception:
                        pass

    def set_program(self, name: str | None) -> None:
        self._program = name or None
        self._start_time = time.time()
        threading.Thread(target=self._update_bg, name="rawview-discord-update", daemon=True).start()

    def _update_bg(self) -> None:
        with self._lock:
            self._push_update()

    def _push_update(self) -> None:
        if self._rpc is None:
            return
        try:
            if self._program:
                self._rpc.update(
                    details=f"Analyzing: {self._program}",
                    state="Reverse Engineering",
                    start=int(self._start_time),
                    large_image="rawview",
                    large_text="RawView",
                )
            else:
                self._rpc.update(
                    details="RawView",
                    state="Idle",
                    start=int(self._start_time),
                    large_image="rawview",
                    large_text="RawView",
                )
        except Exception as exc:
            logger.debug("Discord RPC update failed: %s", exc)
            self._rpc = None

    def close(self) -> None:
        self._stopped.set()
        with self._lock:
            if self._rpc is not None:
                try:
                    self._rpc.close()
                except Exception:
                    pass
                self._rpc = None
