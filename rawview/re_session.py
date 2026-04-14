"""Pack/unpack Ghidra RE session archives (Ghidra project + metadata; excludes Work-dock notes)."""

from __future__ import annotations

import json
import os
import random
import shutil
import string
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

SESSION_JSON = "rawview_re_session.json"
SCHEMA_VERSION = 1
AUTOSAVE_INTERVAL_MS = 300_000  # 5 minutes


def re_recovery_dir() -> Path:
    from rawview.config import user_data_dir

    d = user_data_dir() / "re_recovery"
    d.mkdir(parents=True, exist_ok=True)
    return d


def re_autosave_zip_path() -> Path:
    return re_recovery_dir() / "re_autosave.rvre.zip"


def re_recovery_state_path() -> Path:
    return re_recovery_dir() / "re_state.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_recovery_state() -> dict[str, Any] | None:
    p = re_recovery_state_path()
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_recovery_state(*, clean_shutdown: bool) -> None:
    _atomic_write_json(
        re_recovery_state_path(),
        {"version": 1, "clean_shutdown": clean_shutdown, "saved_at": time.time()},
    )


def mark_re_recovery_clean() -> None:
    """Normal exit: no pending crash snapshot."""
    write_recovery_state(clean_shutdown=True)
    p = re_autosave_zip_path()
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


def mark_re_recovery_dirty() -> None:
    write_recovery_state(clean_shutdown=False)


def build_session_manifest(
    *,
    java_meta: dict[str, str],
    ui: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "projectName": java_meta.get("projectName", ""),
        "programFolder": java_meta.get("programFolder", "/"),
        "programDomainName": java_meta.get("programDomainName", ""),
        "originalBinary": java_meta.get("originalBinary", ""),
        "ui": ui,
    }


def zip_ghidra_project_folder(
    *,
    project_folder: Path,
    manifest: dict[str, Any],
    dest_zip: Path,
) -> None:
    """Write a .rvre.zip with manifest at root and one directory (project name) with all project files."""
    if not project_folder.is_dir():
        raise FileNotFoundError(f"Ghidra project folder not found: {project_folder}")
    root_name = manifest.get("projectName") or project_folder.name
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    part = dest_zip.with_suffix(dest_zip.suffix + ".part")
    if part.is_file():
        part.unlink()
    try:
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(SESSION_JSON, json.dumps(manifest, indent=2))
            for f in project_folder.rglob("*"):
                if f.is_file():
                    arc = f"{root_name}/{f.relative_to(project_folder).as_posix()}"
                    zf.write(f, arcname=arc)
        os.replace(part, dest_zip)
    finally:
        part.unlink(missing_ok=True)


def read_manifest_from_zip(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        try:
            raw = zf.read(SESSION_JSON).decode("utf-8")
        except KeyError as e:
            raise ValueError(f"Missing {SESSION_JSON} in archive") from e
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid session manifest")
    return data


def extract_session_zip(zip_path: Path, dest_parent: Path) -> tuple[Path, dict[str, Any]]:
    """
    Extract archive under dest_parent; returns (extract_root, manifest).
    extract_root contains the Ghidra project directory (manifest['projectName']).
    """
    manifest = read_manifest_from_zip(zip_path)
    pname = str(manifest.get("projectName", "")).strip()
    if not pname:
        raise ValueError("manifest missing projectName")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    extract_root = dest_parent / f"rv_extract_{int(time.time())}_{suffix}"
    extract_root.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_root)
    except Exception:
        shutil.rmtree(extract_root, ignore_errors=True)
        raise
    proj_dir = extract_root / pname
    if not proj_dir.is_dir():
        shutil.rmtree(extract_root, ignore_errors=True)
        raise ValueError(f"Archive did not contain expected folder {pname!r}")
    return extract_root, manifest


def remove_extract_root(extract_root: Path) -> None:
    shutil.rmtree(extract_root, ignore_errors=True)


def unique_import_project_name(project_parent: Path, base: str) -> str:
    """Avoid colliding with an existing Ghidra project directory."""
    if not (project_parent / base).exists():
        return base
    for i in range(1, 10_000):
        cand = f"{base}_{i}"
        if not (project_parent / cand).exists():
            return cand
    return f"{base}_{random.randint(10000, 99999999)}"


def import_project_tree_into_parent(
    *,
    source_project_dir: Path,
    project_parent: Path,
    preferred_name: str | None = None,
) -> tuple[str, Path]:
    """
    Copy a Ghidra project folder into project_parent with a unique name.
    Returns (new_folder_name, new_folder_path).
    """
    base = preferred_name or source_project_dir.name
    base = base.strip() or "rawview_imported"
    name = unique_import_project_name(project_parent, base)
    dest = project_parent / name
    shutil.copytree(source_project_dir, dest)
    return name, dest
