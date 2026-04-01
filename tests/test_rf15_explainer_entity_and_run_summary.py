from __future__ import annotations

from src.erp_fraud.graph import create_initial_graph_state, explainer_node


def test_rf15_explainer_prioritizes_top_k_entities_from_ranking() -> None:
    state = create_initial_graph_state(run_id="rf15-03-topk")
    state.run_metadata["explainer_top_k"] = 1
    state.ranking = [
        {"entity_key": "kreditor=V2|belegnummer=D2", "score_total": 9.0},
        {"entity_key": "kreditor=V1|belegnummer=D1", "score_total": 5.0},
    ]
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 2,
            "columns": ["kreditor", "belegnummer", "betrag"],
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "betrag"],
                },
                {
                    "entity_key": "kreditor=V2|belegnummer=D2",
                    "keys": {"kreditor": "V2", "belegnummer": "D2"},
                    "evidence_columns": ["kreditor", "belegnummer", "betrag"],
                },
            ],
        }
    ]

    out = explainer_node(state)
    assert out.run_metadata["explainer_status"] == "OK"
    assert len(out.explanations) == 1
    assert out.explanations[0]["sample_entity_key"] == "kreditor=V2|belegnummer=D2"


def test_rf15_explainer_writes_run_summary_metadata() -> None:
    state = create_initial_graph_state(run_id="rf15-03-run-summary")
    state.run_metadata["explainer_top_k"] = 2
    state.ranking = [{"entity_key": "kreditor=V1|belegnummer=D1", "score_total": 4.0}]
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 1,
            "columns": ["kreditor", "belegnummer"],
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer"],
                }
            ],
        }
    ]

    out = explainer_node(state)
    summary = out.run_metadata.get("explainer_run_summary", {})
    assert isinstance(summary, dict)
    assert summary["findings_count"] == 1
    assert summary["ranking_available"] is True
    assert summary["explainer_top_k"] == 2
    assert "kreditor=V1|belegnummer=D1" in summary["entities_explained"]
