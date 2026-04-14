"""First-run completion flag: Windows registry (HKCU) or a fallback file under user data."""

from __future__ import annotations

import sys
from pathlib import Path

from rawview.config import user_data_dir

_REG_KEY_PATH = r"Software\RawView"
_REG_VALUE_NAME = "FirstRunTutorialDone"
_FALLBACK_REL = "first_run_tutorial_done"


def _fallback_flag_path() -> Path:
    return user_data_dir() / _FALLBACK_REL


def is_tutorial_complete() -> bool:
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY_PATH, 0, winreg.KEY_READ)
            try:
                val, typ = winreg.QueryValueEx(key, _REG_VALUE_NAME)
            finally:
                winreg.CloseKey(key)
            if typ == winreg.REG_DWORD and int(val) == 1:
                return True
        except OSError:
            pass
    return _fallback_flag_path().is_file()


def mark_tutorial_complete() -> None:
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _REG_KEY_PATH, 0, winreg.KEY_SET_VALUE)
            try:
                winreg.SetValueEx(key, _REG_VALUE_NAME, 0, winreg.REG_DWORD, 1)
            finally:
                winreg.CloseKey(key)
            return
        except OSError:
            pass
    _fallback_flag_path().write_text("1", encoding="utf-8")
