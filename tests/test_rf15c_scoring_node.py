from __future__ import annotations

from src.erp_fraud.graph import create_initial_graph_state, scoring_node
from src.erp_fraud.graph.nodes import _validate_scoring_evidence_and_probability_sum


def test_rf15c_scoring_node_generates_fraud_type_probabilities_with_real_references() -> None:
    state = create_initial_graph_state(run_id="rf15c-10-score-probs")
    state.run_metadata["weights_config"] = "config/weights.yaml"
    state.run_metadata["scoring_top_k"] = 10
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "test_version": "1.0.0",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 3,
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer"],
                    "metrics": {"duplicate_count": 3},
                }
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
    state.selected_tests = [
        {"hypothesis_id": "HYP-001", "test_id": "TST-DUPLICATE-POSTINGS"},
        {"hypothesis_id": "HYP-002", "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR"},
    ]
    state.explanations = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "fraud_type": "duplicate_payment",
            "acfe_reference": {"hits": [{"chunk_id": "acfe-dup-1"}]},
        },
        {
            "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
            "fraud_type": "amount_anomaly",
            "acfe_reference": {"hits": [{"chunk_id": "acfe-amt-1"}]},
        },
    ]

    out = scoring_node(state)
    assert out.run_metadata["scoring_status"] == "OK"
    assert out.run_metadata["scoring_fraud_types"] == 2
    assert len(out.scores) == 1
    payload = out.scores[0]
    probs = payload["fraud_type_probs"]
    assert len(probs) == 2
    prob_sum = sum(float(row["probability"]) for row in probs)
    assert 0.999 <= prob_sum <= 1.001
    dup = next(row for row in probs if row["fraud_type"] == "duplicate_payment")
    amt = next(row for row in probs if row["fraud_type"] == "amount_anomaly")
    assert float(dup["probability"]) > float(amt["probability"])
    assert "TST-DUPLICATE-POSTINGS" in dup["source_test_ids"]
    assert "HYP-001" in dup["source_hypothesis_ids"]
    assert "acfe-dup-1" in dup["acfe_chunk_ids"]

    assert len(out.fraud_type_predicho) == 2
    assert out.fraud_type_predicho[0]["fraud_type"] in {"duplicate_payment", "amount_anomaly"}
    assert isinstance(out.ranking, list) and out.ranking


def test_rf15c_scoring_validator_rejects_invalid_probability_sum_and_fake_evidence() -> None:
    invalid_output = [
        {
            "ranking": [{"entity_key": "k=1"}],
            "fraud_type_probs": [
                {
                    "fraud_type": "duplicate_payment",
                    "probability": 0.8,
                    "source_test_ids": ["TST-DUPLICATE-POSTINGS", "TST-FAKE"],
                },
                {
                    "fraud_type": "amount_anomaly",
                    "probability": 0.3,
                    "source_test_ids": ["TST-UNUSUAL-AMOUNT-BY-VENDOR"],
                },
            ],
        }
    ]
    findings = [
        {"test_id": "TST-DUPLICATE-POSTINGS", "fraud_type": "duplicate_payment"},
        {"test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR", "fraud_type": "amount_anomaly"},
    ]
    validation = _validate_scoring_evidence_and_probability_sum(
        invalid_output,
        {"findings": findings},
    )
    assert validation["passed"] is False
    joined = "\n".join(validation["errors"])
    assert "source_test_ids no presentes en findings" in joined
    assert "suma" in joined
