"""Generación de borradores de data dictionary a partir de schema_summary.json."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ..catalog.test_spec_loader import load_test_specs_from_catalog as load_catalog_test_specs

MIN_DATA_DICTIONARY_ENTRY_FIELDS = (
    "table",
    "column",
    "type",
    "description",
    "examples",
    "used_in_tests",
)


class DataDictionaryCompletenessError(ValueError):
    """Error cuando un TestSpec referencia campos no documentados."""


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_data_dictionary_entry_min_fields(entry: dict) -> dict:
    """Garantiza los campos mínimos requeridos por entrada del diccionario."""
    normalized = dict(entry or {})
    normalized.setdefault("table", "")
    normalized.setdefault("column", "")
    normalized.setdefault("type", "")
    normalized.setdefault("description", "")
    normalized.setdefault("examples", [])
    normalized.setdefault("used_in_tests", [])

    if not isinstance(normalized["examples"], list):
        normalized["examples"] = [normalized["examples"]] if normalized["examples"] not in (None, "") else []
    if not isinstance(normalized["used_in_tests"], list):
        normalized["used_in_tests"] = (
            [normalized["used_in_tests"]] if normalized["used_in_tests"] not in (None, "") else []
        )

    return normalized


def ensure_min_fields_in_data_dictionary(dictionary: dict) -> dict:
    """Asegura campos mínimos y metadato `required_fields` en todo el diccionario."""
    normalized = dict(dictionary or {})
    normalized.setdefault("entry_format", {})
    normalized["entry_format"]["required_fields"] = list(MIN_DATA_DICTIONARY_ENTRY_FIELDS)

    entries = normalized.get("entries", [])
    normalized["entries"] = [normalize_data_dictionary_entry_min_fields(e) for e in entries]
    return normalized


def load_test_specs_from_catalog(catalog_path: str | Path = "tests/catalog") -> list[dict]:
    """Carga TestSpecs desde catálogo sin aplicar validación estricta de RF03."""
    specs = load_catalog_test_specs(catalog_path, validate_schema=False)
    return [dict(spec) for spec in specs]


def _extract_fields_from_data_requirements(data_requirements: Any) -> set[tuple[str, str]]:
    """Extrae pares (table, column) desde estructuras flexibles de TestSpec."""
    pairs: set[tuple[str, str]] = set()
    if not data_requirements:
        return pairs

    # Caso: {"fields": [{"table": "...", "column": "..."}]}
    if isinstance(data_requirements, dict):
        for key in ("fields", "columns"):
            items = data_requirements.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        table = item.get("table") or item.get("table_name")
                        column = item.get("column") or item.get("column_name")
                        if table and column:
                            pairs.add((str(table), str(column)))

        # Caso: {"tables": [{"table": "fraud_1", "columns": ["A", "B"]}]}
        tables_items = data_requirements.get("tables")
        if isinstance(tables_items, list):
            for item in tables_items:
                if not isinstance(item, dict):
                    continue
                table = item.get("table") or item.get("name") or item.get("table_name")
                columns = item.get("columns") or item.get("required_columns")
                if not table or not isinstance(columns, list):
                    continue
                for col in columns:
                    if isinstance(col, str):
                        pairs.add((str(table), col))
                    elif isinstance(col, dict):
                        column = col.get("column") or col.get("name")
                        if column:
                            pairs.add((str(table), str(column)))

        # Caso: {"table_columns": {"fraud_1": ["A","B"]}} o {"fraud_1": ["A","B"]}
        for map_key in ("table_columns", "columns_by_table"):
            by_table = data_requirements.get(map_key)
            if isinstance(by_table, dict):
                for table, cols in by_table.items():
                    if isinstance(cols, list):
                        for col in cols:
                            if isinstance(col, str):
                                pairs.add((str(table), col))

        # Fallback: mapping directo tabla -> [columnas]
        for table, cols in data_requirements.items():
            if table in {"fields", "columns", "tables", "table_columns", "columns_by_table"}:
                continue
            if isinstance(cols, list) and all(isinstance(c, str) for c in cols):
                for col in cols:
                    pairs.add((str(table), col))

    return pairs


def annotate_dictionary_from_tests(
    dictionary: dict,
    *,
    test_specs: list[dict] | None = None,
    catalog_path: str | Path = "tests/catalog",
) -> dict:
    """Rellena `used_in_tests` leyendo `data_requirements` de TestSpecs."""
    normalized = ensure_min_fields_in_data_dictionary(dictionary)
    specs = test_specs if test_specs is not None else load_test_specs_from_catalog(catalog_path)

    usage_index: dict[tuple[str, str], set[str]] = {}
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        test_id = spec.get("id") or spec.get("test_id")
        if not test_id:
            continue
        pairs = _extract_fields_from_data_requirements(spec.get("data_requirements"))
        for table, column in pairs:
            usage_index.setdefault((table, column), set()).add(str(test_id))

    updated_entries: list[dict] = []
    for entry in normalized.get("entries", []):
        e = normalize_data_dictionary_entry_min_fields(entry)
        key = (str(e["table"]), str(e["column"]))
        current = [str(x) for x in e.get("used_in_tests", [])]
        merged = sorted(set(current) | usage_index.get(key, set()))
        e["used_in_tests"] = merged
        updated_entries.append(e)

    normalized["entries"] = updated_entries
    return normalized


def check_dictionary_completeness(
    dictionary: dict,
    *,
    test_specs: list[dict] | None = None,
    catalog_path: str | Path = "tests/catalog",
) -> dict:
    """Valida que todos los campos usados por tests estén documentados.

    Devuelve un resumen. Lanza `DataDictionaryCompletenessError` si falta algún campo.
    """
    normalized = ensure_min_fields_in_data_dictionary(dictionary)
    specs = test_specs if test_specs is not None else load_test_specs_from_catalog(catalog_path)

    documented_fields = {
        (str(e.get("table", "")), str(e.get("column", "")))
        for e in normalized.get("entries", [])
        if e.get("table") and e.get("column")
    }

    missing_by_test: dict[str, list[dict[str, str]]] = {}
    referenced_total = 0
    unique_referenced: set[tuple[str, str]] = set()

    for spec in specs:
        if not isinstance(spec, dict):
            continue
        test_id = str(spec.get("id") or spec.get("test_id") or "")
        if not test_id:
            continue
        pairs = sorted(_extract_fields_from_data_requirements(spec.get("data_requirements")))
        referenced_total += len(pairs)
        unique_referenced.update(pairs)

        missing_for_this_test: list[dict[str, str]] = []
        for table, column in pairs:
            if (table, column) not in documented_fields:
                missing_for_this_test.append({"table": table, "column": column})

        if missing_for_this_test:
            missing_by_test[test_id] = missing_for_this_test

    summary = {
        "status": "OK" if not missing_by_test else "ERROR",
        "tests_analyzed": len([s for s in specs if isinstance(s, dict)]),
        "referenced_fields_total": referenced_total,
        "referenced_fields_unique": len(unique_referenced),
        "documented_fields_total": len(documented_fields),
        "missing_fields_by_test": missing_by_test,
    }

    if missing_by_test:
        fragments: list[str] = []
        for test_id in sorted(missing_by_test.keys()):
            fields = ", ".join(
                f"{item['table']}.{item['column']}" for item in missing_by_test[test_id]
            )
            fragments.append(f"{test_id}: {fields}")
        raise DataDictionaryCompletenessError(
            "El diccionario de datos está incompleto. Campos no documentados usados por tests: "
            + " | ".join(fragments)
        )

    return summary


def build_data_dictionary_draft_from_schema_summary(
    schema_summary: dict,
    *,
    base_dictionary: dict | None = None,
    schema_summary_path: str | Path | None = None,
    generated_at_utc: str | None = None,
) -> dict:
    """Construye un borrador de `data_dictionary.json` desde `schema_summary`.

    Rellena entradas mínimas a partir de tablas/columnas/tipos y deja campos
    descriptivos como placeholders para completar manualmente o en tareas posteriores.
    """
    dictionary = dict(base_dictionary or {})

    dictionary.setdefault("version", "0.1.0")
    dictionary.setdefault(
        "scope",
        {
            "phase": "Fase1",
            "process": "P2P",
            "source": "ERP Fraud Data / joint_datasets",
        },
    )
    dictionary.setdefault(
        "generated_from",
        {
            "schema_summary_json": None,
            "generated_at_utc": None,
        },
    )
    dictionary.setdefault("entry_format", {})
    dictionary["entry_format"]["required_fields"] = list(MIN_DATA_DICTIONARY_ENTRY_FIELDS)

    entries: list[dict] = []
    for table in schema_summary.get("tables", []):
        table_name = table["table_name"]
        for col in sorted(table.get("columns", []), key=lambda c: c.get("ordinal_position", 0)):
            entries.append(
                normalize_data_dictionary_entry_min_fields(
                    {
                    "table": table_name,
                    "column": col["name"],
                    "type": col["type"],
                    "description": "",
                    "examples": [],
                    "used_in_tests": [],
                    "nullable": bool(col.get("nullable", True)),
                    "ordinal_position": int(col.get("ordinal_position", 0)),
                    }
                )
            )

    entries.sort(key=lambda e: (e["table"], e["ordinal_position"], e["column"]))

    dictionary["generated_from"] = {
        "schema_summary_json": str(schema_summary_path) if schema_summary_path else None,
        "generated_at_utc": generated_at_utc or _utc_timestamp_iso(),
    }
    dictionary["entries"] = entries

    return dictionary


def generate_data_dictionary_json_draft(
    schema_summary_path: str | Path,
    *,
    output_path: str | Path = "data_dictionary.json",
) -> Path:
    """Genera/actualiza `data_dictionary.json` a partir de `schema_summary.json`."""
    schema_path = Path(schema_summary_path)
    if not schema_path.exists():
        raise FileNotFoundError(f"No existe schema_summary.json: {schema_path}")

    schema_summary = json.loads(schema_path.read_text(encoding="utf-8"))

    out_path = Path(output_path)
    base_dictionary = None
    if out_path.exists():
        base_dictionary = json.loads(out_path.read_text(encoding="utf-8"))

    draft = build_data_dictionary_draft_from_schema_summary(
        schema_summary,
        base_dictionary=base_dictionary,
        schema_summary_path=schema_path,
    )
    draft = ensure_min_fields_in_data_dictionary(draft)
    out_path.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path
