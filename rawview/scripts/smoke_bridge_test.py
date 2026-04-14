"""Bridge smoke test: start JVM, open a PE, run auto-analysis, list functions. Run from repo root."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    os.environ.setdefault(
        "GHIDRA_INSTALL_DIR",
        str(Path(os.environ["LOCALAPPDATA"]) / "RawView" / "ghidra_bundle" / "ghidra_extract" / "ghidra_12.0.4_PUBLIC"),
    )

    from rawview.config import load_settings
    from rawview.ghidra.api import GhidraAPI
    from rawview.ghidra.bridge import GhidraBridgeController, default_java_executable

    s = load_settings()
    gdir = s.ghidra_install_dir or Path(os.environ["GHIDRA_INSTALL_DIR"])
    jcd = s.rawview_java_classes_dir
    if jcd is None:
        cand = root / "rawview" / "java" / "out"
        if (cand / "io" / "rawview" / "ghidra" / "GhidraServer.class").is_file():
            jcd = cand

    bridge = GhidraBridgeController(
        ghidra_install_dir=gdir,
        java_executable=default_java_executable(s.java_executable, ghidra_install_dir=gdir),
        jvm_max_heap=s.ghidra_jvm_max_heap,
        py4j_port=s.py4j_port,
        project_dir=s.rawview_project_dir,
        java_classes_dir=jcd,
        raw_classpath=s.rawview_java_classpath,
    )
    api = GhidraAPI(bridge=bridge)
    print("starting JVM…", flush=True)
    bridge.start()
    print("ping:", api.ping(), flush=True)
    test_bin = os.environ.get("RAWVIEW_TEST_BINARY", r"C:\Windows\System32\hostname.exe")
    print("open:", test_bin, flush=True)
    name = api.open_file(test_bin)
    print("program:", name, flush=True)
    print("run_auto_analysis…", flush=True)
    api.run_auto_analysis()
    fns = api.list_functions()
    print("function_count:", len(fns), flush=True)
    for f in fns[:12]:
        print(" ", f, flush=True)
    bridge.stop()
    print("TEST_PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
