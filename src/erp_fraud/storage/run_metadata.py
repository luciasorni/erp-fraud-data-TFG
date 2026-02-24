"""Generación de run_metadata.json para ejecuciones del pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_git_head(cwd: str | Path = ".") -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _hash_existing_files(paths: list[Path], *, base_dir: Path) -> str:
    existing = sorted([p for p in paths if p.exists() and p.is_file()])
    if not existing:
        return "not_available"

    digest = hashlib.sha256()
    for path in existing:
        rel = path.relative_to(base_dir) if path.is_relative_to(base_dir) else path
        raw = path.read_bytes()
        digest.update(b"FILE\x00")
        digest.update(str(rel).encode("utf-8"))
        digest.update(b"\x00SIZE\x00")
        digest.update(str(len(raw)).encode("ascii"))
        digest.update(b"\x00CONTENT\x00")
        digest.update(raw)
        digest.update(b"\x00END\x00")
    return digest.hexdigest()


def build_run_metadata(
    *,
    run_id: str,
    dataset_hash: str,
    project_root: str | Path = ".",
    timestamp_utc: str | None = None,
    code_version: str | None = None,
    tests_version: str | None = None,
    config_version: str | None = None,
) -> dict:
    """Construye un metadata dict estable para una ejecución."""
    if not run_id or not run_id.strip():
        raise ValueError("run_id debe ser un string no vacío")
    if not dataset_hash or not dataset_hash.strip():
        raise ValueError("dataset_hash debe ser un string no vacío")

    root = Path(project_root).resolve()

    tests_candidates = [
        root / "tests" / "catalog",
        root / "tests",
    ]
    config_candidates = [
        root / "pyproject.toml",
        root / "requirements.txt",
        root / "requirements-dev.txt",
        root / ".env.example",
        root / "config.yaml",
        root / "config.yml",
        root / "config.json",
    ]

    tests_files: list[Path] = []
    for candidate in tests_candidates:
        if candidate.is_file():
            tests_files.append(candidate)
        elif candidate.is_dir():
            tests_files.extend([p for p in candidate.rglob("*") if p.is_file()])

    metadata = {
        "run_id": run_id.strip(),
        "dataset_hash": dataset_hash.strip(),
        "timestamp_utc": timestamp_utc or _utc_timestamp_iso(),
        "versions": {
            "code": code_version or _safe_git_head(root),
            "tests": tests_version or _hash_existing_files(tests_files, base_dir=root),
            "config": config_version or _hash_existing_files(config_candidates, base_dir=root),
        },
    }
    return metadata


def write_run_metadata_json(
    output_path: str | Path,
    *,
    run_id: str,
    dataset_hash: str,
    project_root: str | Path = ".",
    timestamp_utc: str | None = None,
    code_version: str | None = None,
    tests_version: str | None = None,
    config_version: str | None = None,
) -> Path:
    """Genera `run_metadata.json` con serialización estable."""
    metadata = build_run_metadata(
        run_id=run_id,
        dataset_hash=dataset_hash,
        project_root=project_root,
        timestamp_utc=timestamp_utc,
        code_version=code_version,
        tests_version=tests_version,
        config_version=config_version,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
