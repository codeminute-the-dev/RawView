"""Write packaging/wix/License.rtf from the repository LICENSE (WiX license dialog)."""

from __future__ import annotations

import argparse
from pathlib import Path


def _escape_rtf(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch == "\r":
            continue
        if ch == "\n":
            out.append("\\par ")
            continue
        if ch == "\\":
            out.append("\\\\")
        elif ch == "{":
            out.append("\\{")
        elif ch == "}":
            out.append("\\}")
        elif ord(ch) < 128:
            out.append(ch)
        else:
            # BMP Unicode fallback for WiX / RTF viewers
            out.append(f"\\u{ord(ch)}?")
    return "".join(out)


def build_rtf(license_text: str, footer_note: str) -> str:
    body = _escape_rtf(license_text.strip("\n"))
    footer = _escape_rtf(footer_note.strip("\n"))
    return (
        r"{\rtf1\ansi\deff0{\fonttbl{\f0\fmodern\fcharset0 Consolas;}}"
        r"{\colortbl;\red0\green0\blue0;}"
        r"\f0\fs18 "
        + body
        + r"\par\par "
        + footer
        + "}"
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (parent of packaging/)",
    )
    args = p.parse_args()
    root: Path = args.root
    lic = root / "LICENSE"
    out = root / "packaging" / "wix" / "License.rtf"
    if not lic.is_file():
        raise SystemExit(f"Missing license file: {lic}")
    text = lic.read_text(encoding="utf-8", errors="replace")
    note = (
        "Installer note: Ghidra is not bundled with this MSI; "
        "configure the Ghidra installation path inside RawView."
    )
    out.write_text(build_rtf(text, note), encoding="utf-8", newline="\r\n")


if __name__ == "__main__":
    main()
