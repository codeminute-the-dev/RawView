"""Compile GhidraServer + GhidraBridge against a local Ghidra install (classpath = all Ghidra jars + py4j)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from rawview.config import user_settings_env_path
from rawview.ghidra.bridge import _find_py4j_jar


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _classpath(ghidra_home: Path) -> str:
    sep = ";" if sys.platform == "win32" else ":"
    jars: list[str] = []
    for sub in ("Ghidra", "GPL", "support"):
        p = ghidra_home / sub
        if p.is_dir():
            for jar in p.rglob("*.jar"):
                jars.append(str(jar.resolve()))
    jars = sorted(set(jars))
    py4j_jar = _find_py4j_jar()
    return sep.join(jars + [str(py4j_jar)])


def _javac_from_java(java_exe: str) -> str:
    """``javac`` lives next to ``java`` in the JDK ``bin`` directory."""
    p = Path(java_exe)
    if not p.is_file():
        return "javac"
    name = p.name.lower()
    if name == "java.exe":
        jc = p.parent / "javac.exe"
        return str(jc) if jc.is_file() else "javac"
    if name == "java":
        jc = p.parent / "javac"
        return str(jc) if jc.is_file() else "javac"
    return "javac"


def main() -> int:
    load_dotenv(user_settings_env_path(), override=False)
    load_dotenv(_repo_root() / ".env", override=True)
    ghidra = os.environ.get("GHIDRA_INSTALL_DIR", "").strip()
    if not ghidra:
        print("GHIDRA_INSTALL_DIR is not set. Add it to .env (Ghidra root with Ghidra/ and GPL/). Skip compile.")
        return 0
    gh = Path(ghidra)
    if not gh.is_dir():
        print(f"GHIDRA_INSTALL_DIR is not a directory: {gh}. Skip compile.")
        return 0

    java = shutil_which_java()
    javac = _javac_from_java(java)
    src_dir = _repo_root() / "rawview" / "java" / "io" / "rawview" / "ghidra"
    out_dir = _repo_root() / "rawview" / "java" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    cp = _classpath(gh)
    sources = [
        src_dir / "GhidraServer.java",
        src_dir / "GhidraBridge.java",
        src_dir / "AnalysisProgressMonitor.java",
    ]
    for s in sources:
        if not s.is_file():
            print(f"Missing source: {s}")
            return 1
    cmd = [
        javac,
        "-proc:none",
        "-encoding",
        "UTF-8",
        "-cp",
        cp,
        "-d",
        str(out_dir),
        *[str(s) for s in sources],
    ]
    print("Running:", " ".join(cmd[:6]), "...")
    r = subprocess.run(cmd, check=False)
    if r.returncode != 0:
        return r.returncode
    print(f"OK: class files in {out_dir}")
    print("Set in .env: RAWVIEW_JAVA_CLASSES_DIR=" + str(out_dir))
    return 0


def shutil_which_java() -> str:
    import shutil

    j = shutil.which("java")
    exe = os.environ.get("JAVA_EXECUTABLE", "").strip()
    if exe:
        return exe
    return j or "java"


if __name__ == "__main__":
    raise SystemExit(main())
