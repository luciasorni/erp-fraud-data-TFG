"""Contrato ScoreSchema para RF18 (scoring por tipología con LLM/stub)."""

from __future__ import annotations

from copy import deepcopy


SCORE_SCHEMA_VERSION = "1.0.0"

SCORE_SCHEMA_REQUIRED_FIELDS: tuple[str, ...] = (
    "score_schema_version",
    "generated_at_utc",
    "fraud_type_probs",
    "final_label",
    "confidence",
    "evidence_summary",
    "model_used",
)

SCORE_SCHEMA_FIELD_TYPES: dict[str, tuple[str, ...]] = {
    "score_schema_version": ("str",),
    "generated_at_utc": ("str",),
    "fraud_type_probs": ("list[object]",),
    "final_label": ("str",),
    "confidence": ("float",),
    "evidence_summary": ("str",),
    "model_used": ("str",),
}

SCORE_SCHEMA: dict[str, object] = {
    "title": "ScoreSchema",
    "schema_version": SCORE_SCHEMA_VERSION,
    "required_fields": list(SCORE_SCHEMA_REQUIRED_FIELDS),
    "field_types": dict(SCORE_SCHEMA_FIELD_TYPES),
}


def get_score_schema() -> dict[str, object]:
    """Devuelve una copia del contrato ScoreSchema."""
    return deepcopy(SCORE_SCHEMA)


def get_score_schema_required_fields() -> list[str]:
    """Devuelve los campos obligatorios de ScoreSchema."""
    return list(SCORE_SCHEMA_REQUIRED_FIELDS)
