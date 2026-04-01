from __future__ import annotations

from src.erp_fraud.graph import create_initial_graph_state, scoring_node


def test_rf14_scoring_node_ranks_by_entity_and_fraud_type() -> None:
    state = create_initial_graph_state(run_id="rf14-09-score")
    state.run_metadata["weights_config"] = "config/weights.yaml"
    state.run_metadata["scoring_top_k"] = 10
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "test_version": "1.0.0",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 2,
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "duplicate_count"],
                    "metrics": {"duplicate_count": 2},
                },
                {
                    "entity_key": "kreditor=V2|belegnummer=D2",
                    "keys": {"kreditor": "V2", "belegnummer": "D2"},
                    "evidence_columns": ["kreditor", "belegnummer", "duplicate_count"],
                    "metrics": {"duplicate_count": 3},
                },
            ],
        },
        {
            "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
            "test_version": "1.0.0",
            "fraud_type": "amount_anomaly",
            "status": "OK",
            "finding_count": 1,
            "rows": [
                {
                    "entity_key": "kreditor=V2|belegnummer=D2",
                    "keys": {"kreditor": "V2", "belegnummer": "D2"},
                    "evidence_columns": ["kreditor", "z_score"],
                    "metrics": {"z_score": 4.0},
                }
            ],
        },
    ]

    out = scoring_node(state)

    assert out.run_metadata["scoring_status"] == "OK"
    assert len(out.scores) == 1
    score_payload = out.scores[0]
    ranking = score_payload["ranking"]
    assert len(ranking) == 2
    assert ranking[0]["entity_key"] == "kreditor=V2|belegnummer=D2"
    assert "duplicate_payment" in ranking[0]["fraud_types"]
    assert "amount_anomaly" in ranking[0]["fraud_types"]
    assert score_payload["fraud_type_distribution"]["amount_anomaly"] >= 1
    assert score_payload["fraud_type_distribution"]["duplicate_payment"] >= 1


def test_rf14_scoring_node_no_findings() -> None:
    state = create_initial_graph_state(run_id="rf14-09-empty")
    state.findings = []

    out = scoring_node(state)

    assert out.run_metadata["scoring_status"] == "NO_FINDINGS"
    assert len(out.scores) == 1
    assert out.scores[0]["summary"]["entities_scored"] == 0
    assert out.scores[0]["ranking"] == []

