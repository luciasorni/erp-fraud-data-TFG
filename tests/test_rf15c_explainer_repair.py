from __future__ import annotations

from src.erp_fraud.graph import create_initial_graph_state, explainer_node


def test_rf15c_explainer_retries_with_feedback_and_repairs_hallucinations() -> None:
    state = create_initial_graph_state(run_id="rf15c-09-repair")
    state.run_metadata["explainer_simulate_hallucination_once"] = True
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 1,
            "columns": ["kreditor", "belegnummer", "betrag"],
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "betrag"],
                }
            ],
        }
    ]

    out = explainer_node(state)
    assert out.run_metadata["explainer_status"] == "OK"
    assert len(out.explanations) == 1
    exp = out.explanations[0]
    assert exp["test_id"] == "TST-DUPLICATE-POSTINGS"
    assert exp["cited_test_id"] == "TST-DUPLICATE-POSTINGS"
    assert exp["referenced_columns"] == ["kreditor", "belegnummer", "betrag"]
    assert set(exp["cited_keys"].keys()) == {"kreditor", "belegnummer"}
    assert exp["cited_evidence_columns"] == ["kreditor", "belegnummer", "betrag"]

    alpha_meta = out.run_metadata.get("alphacodium", {})
    assert isinstance(alpha_meta, dict)
    node_meta = alpha_meta.get("expert_explainer", {})
    assert isinstance(node_meta, dict)
    assert int(node_meta.get("iterations", 0)) == 2
