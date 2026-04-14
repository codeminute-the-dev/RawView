"""Application icon path and QIcon helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def app_icon_png_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "app_icon.png"


def load_app_icon() -> QIcon:
    p = app_icon_png_path()
    if p.is_file():
        return QIcon(str(p))
    return QIcon()


def apply_window_icon_to_app(app) -> None:
    """Set default window icon for QApplication (splash + all QMainWindows)."""
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
