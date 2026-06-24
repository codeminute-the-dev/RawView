#!/usr/bin/env bash
# Build RawView as an RPM package (Fedora, RHEL, openSUSE, etc.).
# Requires rpmbuild; installs rpm-build via apt if missing (needs sudo).
#
# Usage (repo root, venv active):
#   source .venv/bin/activate
#   bash build-rpm.sh                      # full build
#   bash build-rpm.sh --skip-pyinstaller   # repackage existing dist/RawView/
#
# Install the result:
#   sudo dnf install dist_installer/rawview-*.rpm
#   sudo rpm -i dist_installer/rawview-*.rpm
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── args ──────────────────────────────────────────────────────────────────────
SKIP_PYINSTALLER=0
for arg in "$@"; do
    case "$arg" in
        --skip-pyinstaller) SKIP_PYINSTALLER=1 ;;
        -h|--help) echo "Usage: bash build-rpm.sh [--skip-pyinstaller]"; exit 0 ;;
    esac
done

# ── version ───────────────────────────────────────────────────────────────────
VERSION=$(grep -m1 'version\s*=' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')
RELEASE="1"
ARCH="x86_64"
RPM_FILENAME="rawview-${VERSION}-${RELEASE}.${ARCH}.rpm"
DIST_BUNDLE="$SCRIPT_DIR/dist/RawView"
OUT_DIR="$SCRIPT_DIR/dist_installer"
RPM_TREE="$SCRIPT_DIR/dist_installer/rpmbuild"
BUILDROOT="$RPM_TREE/BUILDROOT/rawview-${VERSION}-${RELEASE}.${ARCH}"
CHANGELOG_DATE=$(date '+%a %b %d %Y')

echo "=== RawView RPM build ==="
echo "Version : $VERSION-$RELEASE"
echo "Output  : $OUT_DIR/$RPM_FILENAME"
echo ""

# ── step 1: check rpmbuild ────────────────────────────────────────────────────
if ! command -v rpmbuild &>/dev/null; then
    echo "[prereq] rpmbuild not found — installing rpm-build..."
    sudo apt-get install -y rpm-build
fi

# ── step 2: PyInstaller ───────────────────────────────────────────────────────
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

# ── step 3: stage files ───────────────────────────────────────────────────────
echo "[2/4] Staging files..."
rm -rf "$RPM_TREE"
mkdir -p "$RPM_TREE"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
mkdir -p "$BUILDROOT/opt/rawview"
mkdir -p "$BUILDROOT/usr/bin"
mkdir -p "$BUILDROOT/usr/share/applications"
mkdir -p "$BUILDROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILDROOT/usr/share/doc/rawview"

cp -r "$DIST_BUNDLE/." "$BUILDROOT/opt/rawview/"

# Permissions
find "$BUILDROOT/opt/rawview" -type d -exec chmod 755 {} \;
find "$BUILDROOT/opt/rawview" -type f -exec chmod 644 {} \;
chmod 755 "$BUILDROOT/opt/rawview/RawView"
find "$BUILDROOT/opt/rawview" -type f -name "*.so*" -exec chmod 755 {} \;
find "$BUILDROOT/opt/rawview" -type f ! -name "*.*" | while read -r f; do
    if file "$f" 2>/dev/null | grep -qE 'ELF.*(executable|shared object)'; then
        chmod 755 "$f"
    fi
done

# Launcher
cat > "$BUILDROOT/usr/bin/rawview" << 'LAUNCHER'
#!/bin/sh
exec /opt/rawview/RawView "$@"
LAUNCHER
chmod 755 "$BUILDROOT/usr/bin/rawview"

# Icon
if [ -f "$SCRIPT_DIR/rawview/qt_ui/resources/app_icon.png" ]; then
    cp "$SCRIPT_DIR/rawview/qt_ui/resources/app_icon.png" \
       "$BUILDROOT/usr/share/icons/hicolor/256x256/apps/rawview.png"
fi

# Desktop file
cat > "$BUILDROOT/usr/share/applications/rawview.desktop" << DESKTOP
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
chmod 644 "$BUILDROOT/usr/share/applications/rawview.desktop"

# License / copyright
if [ -f "$SCRIPT_DIR/LICENSE" ]; then
    cp "$SCRIPT_DIR/LICENSE" "$BUILDROOT/usr/share/doc/rawview/copyright"
    chmod 644 "$BUILDROOT/usr/share/doc/rawview/copyright"
fi

# ── step 4: SPEC file ─────────────────────────────────────────────────────────
echo "[3/4] Writing SPEC file..."
cat > "$RPM_TREE/SPECS/rawview.spec" << SPEC
Name:           rawview
Version:        ${VERSION}
Release:        ${RELEASE}
Summary:        Qt + Ghidra reverse engineering desktop UI
License:        MIT
URL:            https://github.com/codeminute-the-dev/RawView
BuildArch:      ${ARCH}
AutoReqProv:    no

Requires:       libGL.so.1()(64bit)
Requires:       fontconfig
Requires:       dbus-libs
Requires:       libxcb
Requires:       glib2
Requires:       libxkbcommon

%description
RawView is a desktop application for manual reverse engineering.
It wraps Ghidra headless analysis in a Qt-based UI offering a
decompiler, disassembly view, control flow graph, hex viewer, string
and symbol tables, cross-reference browser, and an AI agent backed by
the Anthropic API.

Ghidra and a JDK are downloaded automatically on first launch.
An Anthropic API key is required for the AI agent feature.

%install
# Files are pre-staged by build-rpm.sh; nothing to do here.

%files
%defattr(-,root,root,-)
/opt/rawview/
/usr/bin/rawview
/usr/share/applications/rawview.desktop
/usr/share/icons/hicolor/256x256/apps/rawview.png
%doc /usr/share/doc/rawview/copyright

%changelog
* ${CHANGELOG_DATE} RawView <noreply@rawview> - ${VERSION}-${RELEASE}
- Initial RPM package
SPEC

# ── step 5: build RPM ─────────────────────────────────────────────────────────
echo "[4/4] Running rpmbuild..."
mkdir -p "$OUT_DIR"
rpmbuild -bb \
    --define "_topdir $RPM_TREE" \
    --buildroot "$BUILDROOT" \
    --define "_rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm" \
    "$RPM_TREE/SPECS/rawview.spec"

# Copy RPM to dist_installer
find "$RPM_TREE/RPMS" -name "*.rpm" -exec cp {} "$OUT_DIR/" \;

echo ""
echo "Done: $OUT_DIR/$RPM_FILENAME"
echo ""
echo "Install:"
echo "  sudo dnf install $OUT_DIR/$RPM_FILENAME"
echo "  sudo rpm -i $OUT_DIR/$RPM_FILENAME"
