#!/usr/bin/env bash
# Build RawView as a standalone PyInstaller bundle on Linux.
# Run from the repo root with the venv active:
#   source .venv/bin/activate
#   bash build-linux.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== RawView Linux build ==="

if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install "pyinstaller>=6.0"
fi

# Compile the Java bridge if GHIDRA_INSTALL_DIR is set and classes are missing.
MARKER="rawview/java/out/io/rawview/ghidra/GhidraServer.class"
if [ -n "${GHIDRA_INSTALL_DIR:-}" ] && [ ! -f "$MARKER" ]; then
    echo "Compiling Java bridge classes..."
    python -m rawview.scripts.compile_java
fi

echo "Running PyInstaller..."
pyinstaller packaging/rawview.spec --noconfirm

echo ""
echo "Done. Bundle: dist/RawView/"
echo "Run with:  ./dist/RawView/RawView"
