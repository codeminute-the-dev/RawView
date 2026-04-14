"""Download a portable Eclipse Temurin JDK (Adoptium) for RawView when no JVM is available."""

from __future__ import annotations

import io
import logging
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from rawview.ghidra_bootstrap import _ssl_context

logger = logging.getLogger(__name__)

ProgressCb = Callable[[int, int, str], None]

# Matches typical Ghidra 12.x requirements (LTS).
DEFAULT_TEMURIN_FEATURE_VERSION = 21

_ADOPTIUM_BASE = "https://api.adoptium.net/v3/binary/latest"


def adoptium_os_arch() -> tuple[str, str]:
    """Return (adoptium_os, adoptium_arch) for Temurin builds."""
    s = sys.platform
    machine = platform.machine().lower()
    if s == "win32":
        if machine not in ("amd64", "x86_64"):
            raise RuntimeError("Bundled JDK download needs 64-bit Windows (x64).")
        return "windows", "x64"
    if s == "darwin":
        if machine in ("arm64", "aarch64"):
            return "mac", "aarch64"
        if machine in ("x86_64", "amd64"):
            return "mac", "x64"
        raise RuntimeError(f"Unsupported macOS CPU: {machine}")
    if s == "linux":
        if machine in ("aarch64", "arm64"):
            return "linux", "aarch64"
        if machine in ("x86_64", "amd64"):
            return "linux", "x64"
        raise RuntimeError(f"Unsupported Linux CPU: {machine}")
    raise RuntimeError(f"Bundled JDK download is not supported on {s!r}.")


def _temurin_download_url(*, feature_version: int = DEFAULT_TEMURIN_FEATURE_VERSION) -> str:
    os_key, arch_key = adoptium_os_arch()
    return (
        f"{_ADOPTIUM_BASE}/{feature_version}/ga/{os_key}/{arch_key}/jdk/hotspot/normal/eclipse"
        "?project=jdk"
    )


def _find_java_binary(extract_root: Path) -> Path | None:
    exe = "java.exe" if sys.platform == "win32" else "java"
    for child in sorted(extract_root.iterdir()):
        if not child.is_dir():
            continue
        candidate = child / "bin" / exe
        if candidate.is_file():
            return candidate.resolve()
    for p in extract_root.rglob(exe):
        if p.is_file() and p.parent.name == "bin":
            return p.resolve()
    return None


def _extract_archive(archive: Path, dest: Path) -> None:
    if dest.is_dir():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    magic = archive.read_bytes()[:4]
    if magic.startswith(b"PK"):
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest)
        return
    with tarfile.open(archive, "r:*") as tf:
        if sys.version_info >= (3, 12):
            tf.extractall(dest, filter=tarfile.data_filter)
        else:
            tf.extractall(dest)


def download_temurin_jdk(
    *,
    dest_parent: Path,
    progress: ProgressCb | None = None,
    feature_version: int = DEFAULT_TEMURIN_FEATURE_VERSION,
) -> Path:
    """
    Download Eclipse Temurin (OpenJDK) and extract it under ``dest_parent``.

    Returns the absolute path to ``java`` / ``java.exe`` to use as ``JAVA_EXECUTABLE``.
    """
    dest_parent.mkdir(parents=True, exist_ok=True)
    progress = progress or (lambda a, b, c: None)
    url = _temurin_download_url(feature_version=feature_version)
    progress(0, 1, f"Downloading Eclipse Temurin JDK {feature_version} (official Adoptium build)…")
    req = urllib.request.Request(url, headers={"User-Agent": "RawView/1.0"})
    ctx = _ssl_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        buf = io.BytesIO()
        done = 0
        chunk = 256 * 1024
        while True:
            part = resp.read(chunk)
            if not part:
                break
            buf.write(part)
            done += len(part)
            if total:
                progress(done, total, f"Downloading JDK… {done // (1024 * 1024)} MB")
            else:
                progress(done, done + 1, f"Downloading JDK… {done // (1024 * 1024)} MB")

    magic = buf.getvalue()[:4]
    suffix = ".zip" if magic.startswith(b"PK") else ".tar.gz"
    archive_path = dest_parent / f"temurin{feature_version}_download{suffix}"
    progress(done, max(done, 1), "Saving archive…")
    archive_path.write_bytes(buf.getvalue())

    extract_root = dest_parent / f"temurin{feature_version}_extract"
    progress(0, 1, "Extracting JDK…")
    _extract_archive(archive_path, extract_root)
    archive_path.unlink(missing_ok=True)

    java_bin = _find_java_binary(extract_root)
    if java_bin is None:
        raise RuntimeError("Extracted JDK archive did not contain bin/java (unexpected layout).")
    logger.info("Temurin JDK ready: %s", java_bin)
    progress(1, 1, f"JDK installed at {java_bin}")
    return java_bin
