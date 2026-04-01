from __future__ import annotations

from src.erp_fraud.catalog import (
    SCORE_SCHEMA_VERSION,
    get_score_schema,
    get_score_schema_required_fields,
)


def test_rf18_score_schema_contract_has_required_fields() -> None:
    schema = get_score_schema()
    required = get_score_schema_required_fields()

    assert schema["title"] == "ScoreSchema"
    assert schema["schema_version"] == SCORE_SCHEMA_VERSION
    assert required == [
        "score_schema_version",
        "generated_at_utc",
        "fraud_type_probs",
        "final_label",
        "confidence",
        "evidence_summary",
        "model_used",
    ]


def test_rf18_score_schema_contract_is_defensive_copy() -> None:
    a = get_score_schema()
    b = get_score_schema()
    assert a is not b
    a["title"] = "mutated"
    assert b["title"] == "ScoreSchema"
