# PyInstaller spec - run from repo root:  pyinstaller packaging\rawview.spec
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# SPECPATH is the spec’s directory (PyInstaller); if it ever points at the file, normalize.
_p = Path(SPECPATH).resolve()
_spec_dir = _p.parent if _p.is_file() else _p
REPO_ROOT = _spec_dir.parent

# Prefer live sources; fall back to setuptools' build/lib copy (e.g. sparse checkout / partial tree).
_entry = REPO_ROOT / "rawview" / "__main__.py"
if not _entry.is_file():
    _entry = REPO_ROOT / "build" / "lib" / "rawview" / "__main__.py"
if not _entry.is_file():
    raise SystemExit(
        "Cannot find rawview/__main__.py. From the repo root run:  python -m pip install -e ."
    )

_res = REPO_ROOT / "rawview" / "qt_ui" / "resources"
if not _res.is_dir():
    _res = REPO_ROOT / "build" / "lib" / "rawview" / "qt_ui" / "resources"
datas = []
if _res.is_dir():
    datas.append((str(_res), "rawview/qt_ui/resources"))
binaries: list = []
hiddenimports = [
    "rawview",
    "rawview.qt_ui",
    "rawview.qt_ui.app",
    "rawview.qt_ui.main_window",
    "rawview.agent.brain",
    "rawview.agent.tools",
    "rawview.agent.memory",
    "rawview.agent.long_term_memory",
    "rawview.agent.conversation_summarize",
    "pydantic_settings",
    "dotenv",
    "certifi",
    "anthropic",
    "py4j",
    "psutil",
]

for pkg in ("PySide6", "shiboken6"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

block_cipher = None

a = Analysis(
    [str(_entry)],
    pathex=[str(REPO_ROOT), str(REPO_ROOT / "build" / "lib")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_app_ico = REPO_ROOT / "rawview" / "qt_ui" / "resources" / "app_icon.ico"
_exe_icon = str(_app_ico) if _app_ico.is_file() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RawView",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RawView",
)
