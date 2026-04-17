"""
Educational: same *mechanical* workflow many DLLs use: load library, then call an exported entry.

  1) Windows loads the DLL -> DllMain runs (attach/detach, etc.)
  2) Your code resolves and calls an export (here: Start)

Use ONLY with DLLs you compile yourself for testing. Do not point this at third-party
binaries you do not own, and do not use this pattern for injection into other programs.

Requires: Python 3.x on Windows (ctypes uses LoadLibraryW / GetProcAddress under the hood).
"""

from __future__ import annotations

import argparse
import ctypes
import sys


def load_and_call_start(dll_path: str, export_name: str = "Start") -> None:
    # CDLL = cdecl; most x64 MSVC exports use the default x64 calling convention.
    handle = ctypes.WinDLL(dll_path)
    proc = getattr(handle, export_name)
    proc.argtypes = []
    proc.restype = None
    proc()


def main() -> int:
    p = argparse.ArgumentParser(description="Load a DLL and call an export (default: Start).")
    p.add_argument(
        "dll",
        help="Path to a DLL *you built* (e.g. demo_plugin.dll from demo_plugin.c).",
    )
    p.add_argument(
        "--export",
        default="Start",
        help="Exported symbol to call (default: Start).",
    )
    args = p.parse_args()
    try:
        load_and_call_start(args.dll, args.export)
    except OSError as e:
        print(f"Load failed: {e}", file=sys.stderr)
        return 1
    except AttributeError:
        print(f"Export '{args.export}' not found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
