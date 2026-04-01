from __future__ import annotations

from src.erp_fraud.graph import run_graph_stub
from src.erp_fraud.graph.evaluators import evaluate_rf14b_automatic


def test_rf14b05_evaluation_attached_to_stub_run() -> None:
    state = run_graph_stub(run_id="rf14b-05-stub", dataset_hash="hash")
    payload = state.run_metadata.get("rf14b_evaluation", {})
    assert isinstance(payload, dict)
    assert payload.get("version") == "1.0.0"
    assert payload.get("checks_total") == 4
    checks = payload.get("checks", [])
    assert isinstance(checks, list)
    assert any(isinstance(row, dict) and row.get("id") == "schema_allowlist_compliance" for row in checks)
    assert any(isinstance(row, dict) and row.get("id") == "no_invented_columns_or_test_ids" for row in checks)
    assert any(isinstance(row, dict) and row.get("id") == "kb_citations_present" for row in checks)
    assert any(isinstance(row, dict) and row.get("id") == "fraud_correspondence" for row in checks)


def test_rf14b05_no_invented_columns_evaluator_fails_when_explainer_invents() -> None:
    state = run_graph_stub(run_id="rf14b-05-invented", dataset_hash="hash")
    assert state.explanations and isinstance(state.explanations[0], dict)
    state.explanations[0]["referenced_columns"] = ["NO_EXISTE_COL"]
    payload = evaluate_rf14b_automatic(state)
    checks = payload.get("checks", [])
    no_invented = next(
        (row for row in checks if isinstance(row, dict) and row.get("id") == "no_invented_columns_or_test_ids"),
        {},
    )
    assert isinstance(no_invented, dict)
    assert no_invented.get("passed") is False


def test_rf14b06_fraud_correspondence_fails_when_final_label_not_in_findings() -> None:
    state = run_graph_stub(run_id="rf14b-06-correspondence", dataset_hash="hash")
    assert state.scores and isinstance(state.scores[0], dict)
    state.scores[0]["final_label"] = "invented_fraud_type"
    state.scores[0]["fraud_type_probs"] = [
        {"fraud_type": "invented_fraud_type", "probability": 1.0},
    ]
    payload = evaluate_rf14b_automatic(state)
    checks = payload.get("checks", [])
    corr = next(
        (row for row in checks if isinstance(row, dict) and row.get("id") == "fraud_correspondence"),
        {},
    )
    assert isinstance(corr, dict)
    assert corr.get("passed") is False
