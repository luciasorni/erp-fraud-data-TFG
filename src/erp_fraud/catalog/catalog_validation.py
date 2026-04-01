"""Validación ampliada del catálogo RF13 (campos + evidence_columns vs schema)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_TESTSPEC_FIELDS_RF13: tuple[str, ...] = (
    "fraud_type",
    "red_flag_id",
    "process_step",
    "expected_output",
    "evidence_columns",
)


class CatalogValidationError(ValueError):
    """Error de validación del catálogo de tests."""


def _load_red_flags_by_id(red_flags_mapping_path: str | Path) -> dict[str, dict[str, str]]:
    path = Path(red_flags_mapping_path)
    if not path.exists():
        raise CatalogValidationError(f"No existe mapping de red flags: {path}")

    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise CatalogValidationError("No se puede validar red flags sin PyYAML instalado") from exc

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CatalogValidationError(f"Mapping de red flags inválido (objeto esperado): {path}")
    red_flags = payload.get("red_flags")
    if not isinstance(red_flags, list) or not red_flags:
        raise CatalogValidationError(f"Mapping de red flags sin lista válida 'red_flags': {path}")

    out: dict[str, dict[str, str]] = {}
    for idx, item in enumerate(red_flags):
        if not isinstance(item, dict):
            raise CatalogValidationError(f"red_flags[{idx}] inválido: debe ser objeto")
        red_flag_id = str(item.get("red_flag_id", "")).strip()
        fraud_type = str(item.get("fraud_type", "")).strip()
        if not red_flag_id:
            raise CatalogValidationError(f"red_flags[{idx}] sin red_flag_id")
        if not fraud_type:
            raise CatalogValidationError(f"{red_flag_id}: falta fraud_type en mapping")
        if red_flag_id in out:
            raise CatalogValidationError(f"red_flag_id duplicado en mapping: {red_flag_id}")
        out[red_flag_id] = {
            "fraud_type": fraud_type,
        }
    return out


def _build_schema_columns_by_table(schema_summary_payload: dict[str, Any]) -> dict[str, set[str]]:
    if not isinstance(schema_summary_payload, dict):
        raise CatalogValidationError("schema_summary inválido: se esperaba objeto")
    tables = schema_summary_payload.get("tables")
    if not isinstance(tables, list):
        raise CatalogValidationError("schema_summary inválido: falta lista 'tables'")

    out: dict[str, set[str]] = {}
    for table_item in tables:
        if not isinstance(table_item, dict):
            continue
        table_name = str(table_item.get("table_name", "")).strip()
        if not table_name:
            continue
        columns = table_item.get("columns", [])
        if not isinstance(columns, list):
            continue
        column_names: set[str] = set()
        for col in columns:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name", col.get("column_name", ""))).strip()
            if name:
                column_names.add(name)
        out[table_name] = column_names
    return out


def validate_catalog_against_schema_summary(
    *,
    test_specs: list[dict[str, Any]],
    schema_summary_payload: dict[str, Any],
    red_flags_mapping_path: str | Path = "config/red_flags_mapping.yaml",
) -> None:
    """Valida campos obligatorios RF13 y evidence_columns contra schema_summary."""
    if not isinstance(test_specs, list):
        raise CatalogValidationError("test_specs inválido: se esperaba lista")

    columns_by_table = _build_schema_columns_by_table(schema_summary_payload)
    if not columns_by_table:
        raise CatalogValidationError("schema_summary sin tablas/columnas para validar catálogo")
    red_flags_by_id = _load_red_flags_by_id(red_flags_mapping_path)

    errors: list[str] = []
    for spec in test_specs:
        if not isinstance(spec, dict):
            errors.append("TestSpec inválido: item no es objeto")
            continue
        test_id = str(spec.get("id", "<sin-id>"))

        missing_fields = [
            field
            for field in REQUIRED_TESTSPEC_FIELDS_RF13
            if field not in spec or spec.get(field) in (None, "", [])
        ]
        if missing_fields:
            errors.append(f"{test_id}: faltan campos obligatorios RF13: {missing_fields}")
            continue

        red_flag_id = str(spec.get("red_flag_id", "")).strip()
        if not red_flag_id:
            errors.append(f"{test_id}: red_flag_id vacío o inválido")
            continue
        red_flag_info = red_flags_by_id.get(red_flag_id)
        if red_flag_info is None:
            errors.append(f"{test_id}: red_flag_id '{red_flag_id}' no existe en mapping")
            continue
        spec_fraud_type = str(spec.get("fraud_type", "")).strip().lower()
        mapping_fraud_type = str(red_flag_info.get("fraud_type", "")).strip().lower()
        if spec_fraud_type != mapping_fraud_type:
            errors.append(
                f"{test_id}: red_flag_id '{red_flag_id}' incoherente con fraud_type "
                f"(spec='{spec_fraud_type}' mapping='{mapping_fraud_type}')"
            )
            continue

        data_requirements = spec.get("data_requirements", {})
        tables_req = data_requirements.get("tables", []) if isinstance(data_requirements, dict) else []
        if not isinstance(tables_req, list) or not tables_req:
            errors.append(f"{test_id}: data_requirements.tables vacío o inválido")
            continue

        referenced_tables: list[str] = []
        for table_req in tables_req:
            if not isinstance(table_req, dict):
                continue
            table_name = str(table_req.get("table", "")).strip()
            if not table_name:
                continue
            referenced_tables.append(table_name)
            if table_name not in columns_by_table:
                errors.append(f"{test_id}: tabla requerida no existe en schema_summary: {table_name}")

        evidence_columns = spec.get("evidence_columns", [])
        if not isinstance(evidence_columns, list) or not evidence_columns:
            errors.append(f"{test_id}: evidence_columns vacío o inválido")
            continue

        for column_name in evidence_columns:
            if not isinstance(column_name, str) or not column_name.strip():
                errors.append(f"{test_id}: evidence_columns contiene valor inválido: {column_name!r}")
                continue
            col = column_name.strip()
            exists_in_any_referenced = any(
                col in columns_by_table.get(table_name, set()) for table_name in referenced_tables
            )
            if not exists_in_any_referenced:
                errors.append(
                    f"{test_id}: evidence_column '{col}' no existe en tablas requeridas {referenced_tables}"
                )

    if errors:
        joined = "\n - ".join(errors)
        raise CatalogValidationError(f"Validación de catálogo RF13 falló:\n - {joined}")
