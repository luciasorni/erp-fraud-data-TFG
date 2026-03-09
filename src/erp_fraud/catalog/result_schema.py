"""Contrato común de ResultSchema para outputs por test (RF05-01)."""

from __future__ import annotations

from copy import deepcopy

RESULT_SCHEMA_VERSION = "1.0.0"

RESULT_SCHEMA_REQUIRED_FIELDS: tuple[str, ...] = (
    "result_schema_version",
    "generated_at_utc",
    "test_id",
    "test_version",
    "fraud_type",
    "status",
    "finding_count",
    "duration_ms",
    "columns",
    "rows",
    "metadata",
)

# Campos previstos en RF05 para trazabilidad de evidencias.
RESULT_SCHEMA_EXTENDED_FIELDS: tuple[str, ...] = (
    "entity_key",
    "keys",
    "evidence_columns",
    "metrics",
)

RESULT_SCHEMA_FIELD_TYPES: dict[str, tuple[str, ...]] = {
    "result_schema_version": ("str",),
    "generated_at_utc": ("str",),
    "test_id": ("str",),
    "test_version": ("str",),
    "fraud_type": ("str",),
    "status": ("str",),
    "finding_count": ("int",),
    "duration_ms": ("int",),
    "columns": ("list[str]",),
    "rows": ("list[object]",),
    "metadata": ("object",),
    "entity_key": ("str", "null"),
    "keys": ("object", "null"),
    "evidence_columns": ("list[str]", "null"),
    "metrics": ("object", "null"),
}

RESULT_SCHEMA: dict[str, object] = {
    "title": "ResultSchema",
    "schema_version": RESULT_SCHEMA_VERSION,
    "required_fields": list(RESULT_SCHEMA_REQUIRED_FIELDS),
    "extended_fields": list(RESULT_SCHEMA_EXTENDED_FIELDS),
    "field_types": dict(RESULT_SCHEMA_FIELD_TYPES),
}


def get_result_schema() -> dict[str, object]:
    """Devuelve una copia del contrato de ResultSchema."""
    return deepcopy(RESULT_SCHEMA)


def get_result_schema_required_fields() -> list[str]:
    """Devuelve los campos obligatorios del ResultSchema."""
    return list(RESULT_SCHEMA_REQUIRED_FIELDS)

