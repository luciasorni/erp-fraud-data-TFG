"""Registro y resolución de fuentes KB para RF15e."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class KBSourcesConfigError(ValueError):
    """Error de configuración de fuentes KB."""


def load_kb_sources_config(path: str | Path = "config/kb_sources.yaml") -> dict[str, Any]:
    """Carga y valida mínimamente el registro de fuentes KB."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe config KB sources: {resolved}")
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc

    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise KBSourcesConfigError("kb_sources.yaml debe contener objeto raíz")

    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise KBSourcesConfigError("kb_sources.yaml: 'sources' debe ser lista no vacía")

    seen_ids: set[str] = set()
    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            raise KBSourcesConfigError(f"sources[{idx}] debe ser objeto")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise KBSourcesConfigError(f"sources[{idx}].source_id inválido")
        if source_id in seen_ids:
            raise KBSourcesConfigError(f"source_id duplicado: {source_id}")
        seen_ids.add(source_id)

        stype = source.get("type")
        if stype not in {"file", "glob"}:
            raise KBSourcesConfigError(f"{source_id}: type debe ser 'file' o 'glob'")
        path_value = source.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise KBSourcesConfigError(f"{source_id}: path inválido")

    return payload


def resolve_kb_sources(
    *,
    config_payload: dict[str, Any],
    base_dir: str | Path = ".",
    include_disabled: bool = False,
) -> dict[str, Any]:
    """Resuelve fuentes existentes/faltantes desde config de KB."""
    root = Path(base_dir)
    sources = config_payload.get("sources", [])
    if not isinstance(sources, list):
        raise KBSourcesConfigError("config_payload.sources debe ser lista")

    resolved_sources: list[dict[str, Any]] = []
    missing_required: list[str] = []

    for source in sources:
        if not isinstance(source, dict):
            continue
        enabled = bool(source.get("enabled", True))
        if not enabled and not include_disabled:
            continue

        source_id = str(source.get("source_id", "")).strip()
        source_type = str(source.get("type", "")).strip()
        source_path = str(source.get("path", "")).strip()
        required = bool(source.get("required", False))

        matched: list[str] = []
        if source_type == "file":
            candidate = root / source_path
            if candidate.exists() and candidate.is_file():
                matched = [str(candidate)]
        elif source_type == "glob":
            matched = [
                str(path)
                for path in sorted(root.glob(source_path))
                if path.is_file()
            ]

        status = "FOUND" if matched else "MISSING"
        resolved_sources.append(
            {
                "source_id": source_id,
                "required": required,
                "type": source_type,
                "path": source_path,
                "status": status,
                "matched_files": matched,
                "matched_count": len(matched),
            }
        )
        if required and not matched:
            missing_required.append(source_id)

    return {
        "resolved_sources": resolved_sources,
        "missing_required_source_ids": missing_required,
        "all_required_available": len(missing_required) == 0,
    }
