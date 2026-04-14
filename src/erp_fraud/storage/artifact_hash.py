"""Cálculo reproducible de artifact_hash (RF14c-09)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


VALID_PROCESS_SCOPES = {"p2p", "o2c", "both"}

# Globs por dominio funcional y tipo de artefacto.
# Solo entradas que afectan comportamiento (prompts, catálogos, mappings y docs KB).
DEFAULT_SCOPE_GLOBS: dict[str, dict[str, tuple[str, ...]]] = {
    "shared": {
        "prompts": ("prompts/*.md",),
        "catalogs": (),
        "mappings": (),
        "docs_kb": ("docs/external/*.pdf", "docs/*.md"),
    },
    "p2p": {
        "prompts": ("prompts/p2p/**/*.md",),
        "catalogs": ("tests/catalog/*.yaml",),
        "mappings": ("mappings/p2p/**/*.yaml", "config/column_mapping_p2p.yaml"),
        "docs_kb": ("docs/p2p/**/*",),
    },
    "o2c": {
        "prompts": ("prompts/o2c/**/*.md",),
        "catalogs": ("tests/catalog_o2c/*.yaml",),
        "mappings": (
            "mappings/o2c/**/*.yaml",
            "config/column_mapping_o2c.yaml",
            "config/o2c_entity_identity.yaml",
            "config/canonical_schema_o2c.yaml",
        ),
        "docs_kb": ("docs/o2c/**/*",),
    },
}


def _normalize_process_scope(raw_value: str) -> str:
    value = str(raw_value or "").strip().lower() or "p2p"
    if value not in VALID_PROCESS_SCOPES:
        raise ValueError("process_scope debe ser 'p2p', 'o2c' o 'both'")
    return value


def _scope_domains(process_scope: str) -> tuple[str, ...]:
    scope = _normalize_process_scope(process_scope)
    if scope == "both":
        return ("shared", "p2p", "o2c")
    return ("shared", scope)


def compute_file_sha256(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def collect_artifact_files(
    *,
    project_root: str | Path,
    process_scope: str,
    scope_globs: dict[str, dict[str, tuple[str, ...]]] | None = None,
) -> list[Path]:
    """Recolecta ficheros relevantes para hash según process_scope."""
    root = Path(project_root).resolve()
    globs_by_scope = scope_globs or DEFAULT_SCOPE_GLOBS
    files: dict[str, Path] = {}

    for domain in _scope_domains(process_scope):
        category_globs = globs_by_scope.get(domain, {})
        for patterns in category_globs.values():
            for pattern in patterns:
                for candidate in root.glob(pattern):
                    if candidate.is_file():
                        rel = candidate.relative_to(root).as_posix()
                        files[rel] = candidate

    ordered_rel = sorted(files.keys())
    return [files[rel] for rel in ordered_rel]


def build_artifact_manifest(
    *,
    files: list[Path],
    project_root: str | Path,
) -> list[dict[str, Any]]:
    """Construye manifiesto estable con ruta relativa + hash + tamaño."""
    root = Path(project_root).resolve()
    rows: list[dict[str, Any]] = []
    for path in files:
        rel = path.resolve().relative_to(root).as_posix()
        rows.append(
            {
                "path": rel,
                "sha256": compute_file_sha256(path),
                "size": int(path.stat().st_size),
            }
        )
    rows.sort(key=lambda row: str(row["path"]))
    return rows


def compute_artifact_hash(
    *,
    project_root: str | Path = ".",
    process_scope: str = "p2p",
    scope_globs: dict[str, dict[str, tuple[str, ...]]] | None = None,
) -> dict[str, Any]:
    """Calcula artifact_hash reproducible sobre manifiesto estable."""
    normalized_scope = _normalize_process_scope(process_scope)
    files = collect_artifact_files(
        project_root=project_root,
        process_scope=normalized_scope,
        scope_globs=scope_globs,
    )
    manifest = build_artifact_manifest(files=files, project_root=project_root)
    manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    artifact_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    return {
        "artifact_hash": artifact_hash,
        "process_scope": normalized_scope,
        "file_count": len(manifest),
        "manifest": manifest,
    }

