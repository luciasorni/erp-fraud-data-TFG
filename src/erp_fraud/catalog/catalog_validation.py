"""Validación ampliada del catálogo RF13 (campos + evidence_columns vs schema)."""

from __future__ import annotations

from typing import Any


REQUIRED_TESTSPEC_FIELDS_RF13: tuple[str, ...] = (
    "fraud_type",
    "process_step",
    "expected_output",
    "evidence_columns",
)


class CatalogValidationError(ValueError):
    """Error de validación del catálogo de tests."""


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
) -> None:
    """Valida campos obligatorios RF13 y evidence_columns contra schema_summary."""
    if not isinstance(test_specs, list):
        raise CatalogValidationError("test_specs inválido: se esperaba lista")

    columns_by_table = _build_schema_columns_by_table(schema_summary_payload)
    if not columns_by_table:
        raise CatalogValidationError("schema_summary sin tablas/columnas para validar catálogo")

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
