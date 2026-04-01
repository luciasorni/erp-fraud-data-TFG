from __future__ import annotations

from src.erp_fraud.catalog import (
    EXPLANATION_SCHEMA_VERSION,
    get_explanation_schema,
    get_explanation_schema_required_fields,
)


def test_rf15_explanation_schema_contract_has_required_fields() -> None:
    schema = get_explanation_schema()
    required = get_explanation_schema_required_fields()

    assert schema["title"] == "ExplanationSchema"
    assert schema["schema_version"] == EXPLANATION_SCHEMA_VERSION
    assert required == [
        "test_id",
        "summary",
        "cited_evidence_columns",
        "fraud_type",
        "process_step",
        "acfe_reference",
    ]


def test_rf15_explanation_schema_contract_is_defensive_copy() -> None:
    a = get_explanation_schema()
    b = get_explanation_schema()
    assert a is not b
    a["title"] = "mutated"
    assert b["title"] == "ExplanationSchema"
