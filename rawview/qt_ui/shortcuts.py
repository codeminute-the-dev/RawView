"""Default keyboard shortcuts and load/save of user overrides in ui_state.ini."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut

# id: (description for settings UI, default QKeySequence string)
AGENT_RELATED_SHORTCUT_IDS = frozenset({"focus_agent_prompt", "run_agent", "stop_agent", "toggle_agent_dock"})

SHORTCUT_DEFAULTS: dict[str, tuple[str, str]] = {
    "open_binary": ("Open binary", "Ctrl+O"),
    "open_settings": ("Open settings", "Ctrl+,"),
    "quit": ("Quit", "Ctrl+Q"),
    "next_central_tab": ("Next analysis tab", "Ctrl+Tab"),
    "prev_central_tab": ("Previous analysis tab", "Ctrl+Shift+Tab"),
    "decompiler_tab": ("Go to Decompiler tab", "Ctrl+1"),
    "disasm_tab": ("Go to Disassembly tab", "Ctrl+2"),
    "hex_tab": ("Go to Hex tab", "Ctrl+3"),
    "focus_agent_prompt": ("Focus agent prompt", "Ctrl+L"),
    "run_agent": ("Run agent", "Ctrl+Return"),
    "stop_agent": ("Stop agent", "Ctrl+Shift+S"),
    "run_auto_analysis": ("Run auto-analysis", "Ctrl+Shift+A"),
    "toggle_file_dock": ("Toggle File dock", "Ctrl+Shift+F"),
    "toggle_work_dock": ("Toggle Work dock", "Ctrl+Shift+W"),
    "toggle_agent_dock": ("Toggle Agent dock", "Ctrl+Shift+G"),
}


def load_shortcut_map(ui_settings: QSettings) -> dict[str, str]:
    ui_settings.beginGroup("shortcuts")
    keys = ui_settings.childKeys()
    out: dict[str, str] = {}
    for k in keys:
        v = ui_settings.value(k)
        if isinstance(v, str) and v.strip():
            out[str(k)] = v.strip()
    ui_settings.endGroup()
    return out


def save_shortcut_map(ui_settings: QSettings, mapping: dict[str, str]) -> None:
    ui_settings.beginGroup("shortcuts")
    for k in ui_settings.childKeys():
        ui_settings.remove(k)
    for k, v in mapping.items():
        if v.strip():
            ui_settings.setValue(k, v.strip())
    ui_settings.endGroup()
    ui_settings.sync()


def effective_sequence(sid: str, overrides: dict[str, str]) -> QKeySequence:
    if sid in overrides:
        return QKeySequence(overrides[sid], QKeySequence.SequenceFormat.PortableText)
    _desc, default = SHORTCUT_DEFAULTS[sid]
    return QKeySequence(default, QKeySequence.SequenceFormat.PortableText)


class ShortcutController:
    """Owns QShortcut objects and (re)binds them from QSettings overrides."""

    def __init__(self, parent_window, ui_settings: QSettings) -> None:
        self._win = parent_window
        self._ui = ui_settings
        self._shortcuts: list[QShortcut] = []
        self._handlers: dict[str, Callable[[], None]] = {}

    def register(self, sid: str, handler: Callable[[], None]) -> None:
        self._handlers[sid] = handler

    def apply(self) -> None:
        for s in self._shortcuts:
            s.deleteLater()
        self._shortcuts.clear()
        overrides = load_shortcut_map(self._ui)
        for sid, handler in self._handlers.items():
            if sid not in SHORTCUT_DEFAULTS:
                continue
            seq = effective_sequence(sid, overrides)
            if seq.isEmpty():
                continue
            sc = QShortcut(seq, self._win)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(handler)
            self._shortcuts.append(sc)
