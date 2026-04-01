"""Contrato ExplanationSchema para RF15 (explicador con guardrails)."""

from __future__ import annotations

from copy import deepcopy


EXPLANATION_SCHEMA_VERSION = "1.0.0"

EXPLANATION_SCHEMA_REQUIRED_FIELDS: tuple[str, ...] = (
    "test_id",
    "summary",
    "cited_evidence_columns",
    "fraud_type",
    "process_step",
    "acfe_reference",
)

EXPLANATION_SCHEMA_FIELD_TYPES: dict[str, tuple[str, ...]] = {
    "test_id": ("str",),
    "summary": ("str",),
    "cited_evidence_columns": ("list[str]",),
    "fraud_type": ("str",),
    "process_step": ("str",),
    "acfe_reference": ("object",),
}

EXPLANATION_SCHEMA: dict[str, object] = {
    "title": "ExplanationSchema",
    "schema_version": EXPLANATION_SCHEMA_VERSION,
    "required_fields": list(EXPLANATION_SCHEMA_REQUIRED_FIELDS),
    "field_types": dict(EXPLANATION_SCHEMA_FIELD_TYPES),
    "notes": {
        "summary": "resumen auditor-style de hallazgos",
        "cited_evidence_columns": "evidencias citadas en outputs reales",
        "test_id": "tests del catálogo que respaldan la explicación",
        "fraud_type": "tipología de fraude",
        "process_step": "paso P2P/O2C afectado",
        "acfe_reference": "referencias ACFE (KB hits, source_id/source_path/chunk_id)",
    },
}


def get_explanation_schema() -> dict[str, object]:
    """Devuelve una copia defensiva del contrato ExplanationSchema."""
    return deepcopy(EXPLANATION_SCHEMA)


def get_explanation_schema_required_fields() -> list[str]:
    """Devuelve campos obligatorios de ExplanationSchema."""
    return list(EXPLANATION_SCHEMA_REQUIRED_FIELDS)
