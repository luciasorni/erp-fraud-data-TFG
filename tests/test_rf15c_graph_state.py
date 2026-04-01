from __future__ import annotations

from src.erp_fraud.graph import GraphState, create_initial_graph_state, graph_state_to_dict


def test_rf15c_01_graph_state_contains_extended_multiagent_fields() -> None:
    state = create_initial_graph_state(run_id="rf15c-01-check")
    assert isinstance(state, GraphState)
    assert isinstance(state.test_runs, list)
    assert isinstance(state.ranking, list)
    assert isinstance(state.fraud_type_predicho, list)
    assert isinstance(state.recomendaciones, list)
    assert isinstance(state.export_paths, dict)


def test_rf15c_01_graph_state_serialization_keeps_extended_fields() -> None:
    state = create_initial_graph_state(run_id="rf15c-01-serialize")
    state.test_runs.append({"test_id": "TST-DUPLICATE-POSTINGS", "status": "OK"})
    state.ranking.append({"entity_key": "kreditor=V1|belegnummer=B1", "score_total": 4.2})
    state.fraud_type_predicho.append({"fraud_type": "duplicate_payment", "prob": 0.71})
    state.recomendaciones.append({"test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT", "reason": "match"})
    state.export_paths["ranking_csv"] = "run_results/rf15c-01/exports/ranking.csv"

    payload = graph_state_to_dict(state)
    assert payload["test_runs"][0]["status"] == "OK"
    assert payload["ranking"][0]["entity_key"] == "kreditor=V1|belegnummer=B1"
    assert payload["fraud_type_predicho"][0]["fraud_type"] == "duplicate_payment"
    assert payload["recomendaciones"][0]["test_id"] == "TST-SPLIT-PAYMENTS-NEAR-LIMIT"
    assert payload["export_paths"]["ranking_csv"].endswith("ranking.csv")

