from __future__ import annotations

import json
from pathlib import Path

from src.erp_fraud.catalog import (
    EXPLANATION_SCHEMA_VERSION,
    SCORE_SCHEMA_VERSION,
    get_explanation_schema_required_fields,
    get_score_schema_required_fields,
)
from src.erp_fraud.graph import (
    GRAPH_STATE_SCHEMA_VERSION,
    create_initial_graph_state,
    get_graph_state_contract,
    graph_state_to_dict,
    validate_graph_state_payload,
)
from src.erp_fraud.storage.report_json import (
    REPORT_JSON_VERSION,
    get_report_json_contract,
    validate_report_json_contract,
)


def test_rf14b_p01_contract_versions_are_frozen() -> None:
    assert GRAPH_STATE_SCHEMA_VERSION == "1.0.0"
    assert EXPLANATION_SCHEMA_VERSION == "1.0.0"
    assert SCORE_SCHEMA_VERSION == "1.0.0"
    assert REPORT_JSON_VERSION == "1.0.0"


def test_rf14b_p01_graph_state_payload_matches_contract() -> None:
    state = create_initial_graph_state(run_id="rf14b-p01")
    payload = graph_state_to_dict(state)
    errors = validate_graph_state_payload(payload)
    assert errors == []

    contract = get_graph_state_contract()
    required = set(contract["required_fields"])
    assert required.issubset(set(payload.keys()))


def test_rf14b_p01_report_contract_accepts_legacy_v1_payload() -> None:
    payload = json.loads(Path("tests/fixtures/contracts/report_v1_min.json").read_text(encoding="utf-8"))
    errors = validate_report_json_contract(payload)
    assert errors == []

    contract = get_report_json_contract()
    required = set(contract["required_top_level_fields"])
    assert required.issubset(set(payload.keys()))


def test_rf14b_p01_explanation_and_score_have_required_fields() -> None:
    explanation_required = get_explanation_schema_required_fields()
    score_required = get_score_schema_required_fields()
    for field in ("test_id", "summary", "fraud_type", "acfe_reference"):
        assert field in explanation_required
    for field in ("fraud_type_probs", "final_label", "confidence"):
        assert field in score_required
