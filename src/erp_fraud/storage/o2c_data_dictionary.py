"""Generación de data dictionary O2C desde schema + mapping (RF11-10)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_yaml(path: str | Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyYAML no disponible") from exc
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe YAML: {p}")
    payload = yaml.safe_load(p.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido (raíz no objeto): {p}")
    return payload


def _field_description(entity: str, field_name: str, process_step: str) -> str:
    return (
        f"Campo canónico O2C '{field_name}' de la entidad '{entity}' "
        f"en el paso de proceso '{process_step}'."
    )


def build_o2c_data_dictionary(
    *,
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
    mapping_config_path: str | Path = "config/column_mapping_o2c.yaml",
) -> dict[str, Any]:
    schema_cfg = _load_yaml(canonical_schema_config_path)
    mapping_cfg = _load_yaml(mapping_config_path)

    entities_cfg = schema_cfg.get("entities", {})
    if not isinstance(entities_cfg, dict):
        entities_cfg = {}
    map_entities = mapping_cfg.get("entities", {})
    if not isinstance(map_entities, dict):
        map_entities = {}

    entries: list[dict[str, Any]] = []
    for entity, entity_cfg in sorted(entities_cfg.items()):
        if not isinstance(entity_cfg, dict):
            continue
        process_step = str(entity_cfg.get("process_step", "")).strip()
        required_names: set[str] = set()
        required_types: dict[str, str] = {}
        for row in entity_cfg.get("required_fields", []) if isinstance(entity_cfg.get("required_fields"), list) else []:
            if isinstance(row, dict):
                name = str(row.get("name", "")).strip()
                if name:
                    required_names.add(name)
                    required_types[name] = str(row.get("type", "")).strip()
        optional_types: dict[str, str] = {}
        for row in entity_cfg.get("optional_fields", []) if isinstance(entity_cfg.get("optional_fields"), list) else []:
            if isinstance(row, dict):
                name = str(row.get("name", "")).strip()
                if name:
                    optional_types[name] = str(row.get("type", "")).strip()

        mapping_entity = map_entities.get(entity, {})
        field_map = mapping_entity.get("field_mapping", {}) if isinstance(mapping_entity, dict) else {}
        if not isinstance(field_map, dict):
            field_map = {}

        field_names = sorted(set(required_names) | set(optional_types.keys()) | set(field_map.keys()))
        for ordinal, field_name in enumerate(field_names, start=1):
            mapped = field_map.get(field_name, {})
            if not isinstance(mapped, dict):
                mapped = {}
            source_candidates = mapped.get("source_candidates", [])
            if not isinstance(source_candidates, list):
                source_candidates = []
            source_candidates = [str(x).strip() for x in source_candidates if str(x).strip()]
            field_type = required_types.get(field_name) or optional_types.get(field_name) or str(
                mapped.get("cast", "")
            ).strip()

            entry = {
                "table": entity,
                "column": field_name,
                "type": field_type,
                "description": _field_description(entity, field_name, process_step),
                "examples": [],
                "used_in_tests": [],
                "process_family": "o2c",
                "process_step": process_step,
                "required": field_name in required_names,
                "source_candidates": source_candidates,
                "cast": str(mapped.get("cast", "")).strip(),
                "default": mapped.get("default", None),
                "ordinal_position": ordinal,
            }
            entries.append(entry)

    payload = {
        "version": "1.0.0",
        "scope": {
            "phase": "Fase2",
            "process": "O2C",
            "source": "ERP Fraud Data / raw_data",
        },
        "generated_from": {
            "canonical_schema_config": str(canonical_schema_config_path),
            "mapping_config": str(mapping_config_path),
            "generated_at_utc": _utc_now_iso(),
        },
        "entry_format": {
            "required_fields": [
                "table",
                "column",
                "type",
                "description",
                "examples",
                "used_in_tests",
            ]
        },
        "entries": sorted(entries, key=lambda e: (str(e["table"]), int(e.get("ordinal_position", 0)), str(e["column"]))),
    }
    return payload


def write_o2c_data_dictionary_json(
    output_path: str | Path,
    *,
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
    mapping_config_path: str | Path = "config/column_mapping_o2c.yaml",
) -> Path:
    payload = build_o2c_data_dictionary(
        canonical_schema_config_path=canonical_schema_config_path,
        mapping_config_path=mapping_config_path,
    )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def write_o2c_data_dictionary_markdown(
    output_path: str | Path,
    *,
    dictionary_payload: dict[str, Any],
) -> Path:
    entries = dictionary_payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if isinstance(entry, dict):
            grouped.setdefault(str(entry.get("table", "")), []).append(entry)

    lines: list[str] = []
    lines.append("# Data Dictionary O2C")
    lines.append("")
    lines.append("Generado automáticamente desde schema canónico + mapping O2C.")
    lines.append("")
    lines.append("## Alcance")
    lines.append("")
    scope = dictionary_payload.get("scope", {})
    if not isinstance(scope, dict):
        scope = {}
    lines.append(f"- Proceso: `{scope.get('process', 'O2C')}`")
    lines.append(f"- Fuente: `{scope.get('source', 'ERP Fraud Data / raw_data')}`")
    lines.append("")

    for table in sorted(grouped.keys()):
        if not table:
            continue
        lines.append(f"## Tabla: `{table}`")
        lines.append("")
        rows = sorted(grouped[table], key=lambda e: int(e.get("ordinal_position", 0)))
        for row in rows:
            col = str(row.get("column", "")).strip()
            if not col:
                continue
            lines.append(f"### `{table}.{col}`")
            lines.append("")
            lines.append(f"- `type`: `{row.get('type', '')}`")
            lines.append(f"- `required`: `{bool(row.get('required', False))}`")
            lines.append(f"- `process_step`: `{row.get('process_step', '')}`")
            lines.append(f"- `cast`: `{row.get('cast', '')}`")
            source_candidates = row.get("source_candidates", [])
            if not isinstance(source_candidates, list):
                source_candidates = []
            lines.append(
                "- `source_candidates`: `"
                + ", ".join(str(x) for x in source_candidates)
                + "`"
            )
            lines.append(f"- `default`: `{row.get('default', None)}`")
            lines.append(f"- `description`: {row.get('description', '')}")
            lines.append("")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return out

