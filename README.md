# RawView

RawView is a **native desktop UI** (Qt / PySide6) for manual reverse engineering. It talks to **Ghidra** running headlessly in the background (Java bridge via Py4J) so you can open binaries, run analysis, and use decompiler, disassembly, strings, imports/exports, xrefs, and related panes from one window.

An **optional AI agent** dock can call the same Ghidra bridge when you add an Anthropic API key in **File → Settings**. Nothing else requires the network.

## Is it safe to publish this repository?

**Yes, if you publish the repository root** (the directory that contains this `README.md` and `pyproject.toml`). That is the whole project: packaging, WiX files, scripts, and the `rawview/` Python package. Do **not** publish only the inner `rawview/` folder; you would drop build metadata and the installer tooling.

**What stays out of Git by design** (see `.gitignore`):

- **Secrets**: `.env`, `.env.*`, and `rawview.env` if it ever appears in the tree (normal installs store settings under `%LOCALAPPDATA%\RawView\`, not in the clone).
- **Large downloads**: local `ghidra_bundle/`, `temurin_bundle/`, etc. (the app fetches Ghidra and a JDK into `%LOCALAPPDATA%\RawView\` at runtime; those paths are not part of the repo).
- **Build outputs**: `dist/`, `dist_installer/`, `build/`, `release/`, `rawview/java/out/`, generated WiX harvest files.

**What you should still double-check before pushing**

- No API keys or tokens pasted into tracked files.
- No personal paths you do not want public (some people use machine-specific notes; keep them untracked or outside the repo).

## Requirements

- **Python** 3.11+
- **Windows** is the primary target for the packaged app; development is oriented around the Windows build scripts.
- **Ghidra**: you point RawView at a Ghidra installation (or ZIP URL) in settings; it is **not** redistributed inside this repository.
- **JDK 21+** (e.g. Temurin): used to compile the small Java bridge; the app can download a JDK into AppData on first run, or you install one yourself.

## Run from source

```powershell
cd path\to\RawView
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m rawview.scripts.compile_java
python -m rawview
```

## Windows installer (MSI)

Needs [WiX Toolset 3.11+](https://github.com/wixtoolset/wix3/releases) (`heat.exe` / `candle.exe` / `light.exe` on PATH or `WIX` set to the toolkit root).

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-msi.ps1
```

Produces `dist\RawView\` (PyInstaller onedir) and `dist_installer\RawView-0.1.0.msi`. Use `-SkipPyInstaller` if you only changed WiX and `dist\RawView` is already up to date.

## Source-only zip (no `dist/`)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export-source-zip.ps1
```

Writes a zip next to the repo folder containing exactly what Git tracks.

## Repository layout

| Path | Role |
|------|------|
| `pyproject.toml` | Package metadata and dependencies |
| `rawview/` | Importable Python package and Java **sources** under `rawview/java/` |
| `packaging/` | PyInstaller spec, WiX `Product.wxs`, icon assets |
| `scripts/` | `build-windows.ps1`, `build-msi.ps1`, export helpers |
| `installer/` | Optional Inno Setup script (separate from MSI pipeline) |
| `pip/` | Optional editable-install helpers |
| `LICENSE` | GNU General Public License v3 (full text) |

## License

Licensed under the **GNU General Public License v3.0**; see `LICENSE`.
