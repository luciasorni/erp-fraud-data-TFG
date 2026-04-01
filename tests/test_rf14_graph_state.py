from __future__ import annotations

from src.erp_fraud.graph import GraphState, create_initial_graph_state, graph_state_to_dict


def test_create_initial_graph_state_contains_required_rf14_fields() -> None:
    state = create_initial_graph_state(
        run_id="rf14-01-check",
        dataset_hash="hash-123",
        input_zip="erp_fraud_data.zip",
    )
    assert isinstance(state, GraphState)
    assert state.run_id == "rf14-01-check"
    assert isinstance(state.schema, dict)
    assert isinstance(state.kb_status, dict)
    assert isinstance(state.hypotheses, list)
    assert isinstance(state.selected_tests, list)
    assert isinstance(state.findings, list)
    assert isinstance(state.explanations, list)
    assert isinstance(state.scores, list)
    assert isinstance(state.run_metadata, dict)
    assert state.run_metadata["dataset_hash"] == "hash-123"
    assert state.run_metadata["input_zip"] == "erp_fraud_data.zip"


def test_graph_state_to_dict_keeps_structure() -> None:
    state = create_initial_graph_state(run_id="rf14-01-serialize")
    state.hypotheses.append({"hypothesis_id": "H-001", "text": "Posible split payments"})
    state.selected_tests.append({"hypothesis_id": "H-001", "test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT"})
    payload = graph_state_to_dict(state)
    assert payload["run_id"] == "rf14-01-serialize"
    assert payload["hypotheses"][0]["hypothesis_id"] == "H-001"
    assert payload["selected_tests"][0]["test_id"] == "TST-SPLIT-PAYMENTS-NEAR-LIMIT"
    assert "updated_at_utc" in payload["run_metadata"]

