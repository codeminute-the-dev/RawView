#!/usr/bin/env bash
# Build a .deb package for RawView (amd64, Debian/Ubuntu).
# Runs PyInstaller first, then wraps the bundle into a proper .deb.
#
# Usage (repo root, venv active):
#   source .venv/bin/activate
#   bash build-deb.sh                   # full build
#   bash build-deb.sh --skip-pyinstaller  # package existing dist/RawView/
#
# Install the resulting .deb:
#   sudo dpkg -i dist_installer/rawview_*.deb
#   sudo apt-get install -f             # fix any missing deps
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── args ──────────────────────────────────────────────────────────────────────
SKIP_PYINSTALLER=0
for arg in "$@"; do
    case "$arg" in
        --skip-pyinstaller) SKIP_PYINSTALLER=1 ;;
        -h|--help)
            echo "Usage: bash build-deb.sh [--skip-pyinstaller]"
            exit 0 ;;
    esac
done

# ── version ───────────────────────────────────────────────────────────────────
VERSION=$(grep -m1 'version\s*=' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')
PKG_NAME="rawview"
ARCH="amd64"
DEB_FILENAME="${PKG_NAME}_${VERSION}_${ARCH}.deb"
DIST_BUNDLE="$SCRIPT_DIR/dist/RawView"
DEB_ROOT="$SCRIPT_DIR/dist_installer/deb_root"
OUT_DIR="$SCRIPT_DIR/dist_installer"

echo "=== RawView .deb build ==="
echo "Version : $VERSION"
echo "Output  : $OUT_DIR/$DEB_FILENAME"
echo ""

# ── prereq check ──────────────────────────────────────────────────────────────
if ! command -v dpkg-deb &>/dev/null; then
    echo "ERROR: dpkg-deb not found. Install with: sudo apt install dpkg-dev"
    exit 1
fi

# ── step 1: PyInstaller ───────────────────────────────────────────────────────
if [ "$SKIP_PYINSTALLER" -eq 0 ]; then
    echo "[1/4] Running PyInstaller..."
    bash "$SCRIPT_DIR/build-linux.sh"
else
    echo "[1/4] Skipping PyInstaller (--skip-pyinstaller)."
fi

if [ ! -f "$DIST_BUNDLE/RawView" ]; then
    echo "ERROR: $DIST_BUNDLE/RawView not found."
    echo "       Run without --skip-pyinstaller, or run build-linux.sh first."
    exit 1
fi

# ── step 2: build directory tree ──────────────────────────────────────────────
echo "[2/4] Building .deb directory tree..."
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/opt/rawview"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_ROOT/usr/share/doc/$PKG_NAME"

# Bundle
cp -r "$DIST_BUNDLE/." "$DEB_ROOT/opt/rawview/"

# Set permissions: directories 755, all files 644, then fix executables/libs.
find "$DEB_ROOT/opt/rawview" -type d -exec chmod 755 {} \;
find "$DEB_ROOT/opt/rawview" -type f -exec chmod 644 {} \;
# Main exe + all .so / .so.* files must be executable.
chmod 755 "$DEB_ROOT/opt/rawview/RawView"
find "$DEB_ROOT/opt/rawview" -type f -name "*.so*" -exec chmod 755 {} \;
# ELF binaries without extension (PyInstaller bootloader fragments, etc.)
find "$DEB_ROOT/opt/rawview" -type f ! -name "*.*" | while read -r f; do
    read -rn4 magic < "$f" 2>/dev/null && [[ "$magic" == $'\x7fELF'* ]] && chmod 755 "$f" || true
done

# Launcher wrapper (keeps CWD / env clean)
cat > "$DEB_ROOT/usr/bin/rawview" << 'LAUNCHER'
#!/bin/sh
exec /opt/rawview/RawView "$@"
LAUNCHER
chmod 755 "$DEB_ROOT/usr/bin/rawview"

# Icon
if [ -f "$SCRIPT_DIR/rawview/qt_ui/resources/app_icon.png" ]; then
    cp "$SCRIPT_DIR/rawview/qt_ui/resources/app_icon.png" \
       "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps/rawview.png"
fi

# .desktop entry
cat > "$DEB_ROOT/usr/share/applications/rawview.desktop" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=RawView
Comment=Qt + Ghidra reverse engineering desktop UI
Exec=/opt/rawview/RawView %u
Icon=rawview
Terminal=false
Categories=Development;Debugger;
Keywords=reverse;engineering;ghidra;disassembler;decompiler;binary;
StartupWMClass=RawView
DESKTOP
chmod 644 "$DEB_ROOT/usr/share/applications/rawview.desktop"

# Copyright
if [ -f "$SCRIPT_DIR/LICENSE" ]; then
    cp "$SCRIPT_DIR/LICENSE" "$DEB_ROOT/usr/share/doc/$PKG_NAME/copyright"
    chmod 644 "$DEB_ROOT/usr/share/doc/$PKG_NAME/copyright"
fi

# ── step 3: DEBIAN/control ────────────────────────────────────────────────────
echo "[3/4] Writing DEBIAN/control..."
INSTALLED_KB=$(du -sk "$DEB_ROOT/opt" "$DEB_ROOT/usr" 2>/dev/null \
               | awk '{sum+=$1} END{print sum}')

cat > "$DEB_ROOT/DEBIAN/control" << CONTROL
Package: $PKG_NAME
Version: $VERSION
Architecture: $ARCH
Maintainer: RawView
Installed-Size: $INSTALLED_KB
Depends: libgl1 | libgl1-mesa-glx, libfontconfig1, libdbus-1-3, libxcb1, libglib2.0-0, libxkbcommon0, libxkbcommon-x11-0
Recommends: libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-xinerama0, libxcb-xkb1
Section: devel
Priority: optional
Homepage: https://github.com/codeminute-the-dev/RawView
Description: Qt + Ghidra reverse engineering desktop UI
 RawView is a desktop application for manual reverse engineering.
 It wraps Ghidra headless analysis in a Qt-based UI offering a
 decompiler, disassembly view, control flow graph, hex viewer, string
 and symbol tables, cross-reference browser, and an AI agent backed by
 the Anthropic API.
 .
 Ghidra and a JDK are downloaded automatically on first launch.
 An Anthropic API key is required for the AI agent feature.
CONTROL
chmod 644 "$DEB_ROOT/DEBIAN/control"

# ── step 4: build .deb ────────────────────────────────────────────────────────
echo "[4/4] Building .deb with dpkg-deb..."
mkdir -p "$OUT_DIR"
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$OUT_DIR/$DEB_FILENAME"

echo ""
echo "Done: $OUT_DIR/$DEB_FILENAME"
echo ""
echo "Install:"
echo "  sudo dpkg -i $OUT_DIR/$DEB_FILENAME"
echo "  sudo apt-get install -f   # resolve any missing deps"
echo ""
echo "Run: rawview"
