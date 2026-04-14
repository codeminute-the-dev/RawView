# Install RawView with pip

All commands use the **repository root** (parent of this `pip` folder), where `pyproject.toml` lives.

## Quick (Windows)

From this folder:

- **Double-click or run** `install.bat`, or  
- **PowerShell:** `.\install.ps1`

## Manual

**Editable** (recommended while developing - changes in the clone apply immediately):

```text
cd ..
pip install -e .
```

From anywhere:

```text
pip install -e C:\path\to\RawView
```

**From this folder using the requirements file:**

```text
pip install -r requirements-editable.txt
```

Paths in that file are resolved relative to the file’s directory, so `-e ..` is the repo root.

## Optional dev extra

```text
cd ..
pip install -e ".[dev]"
```

## After install

- Run the app: `rawview` (console script), or `python -m rawview`.
- Ghidra + compiled Java: configure in **File → Settings** or env vars; compile helpers live under `rawview/scripts/`.
