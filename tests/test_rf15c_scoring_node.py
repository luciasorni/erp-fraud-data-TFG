from __future__ import annotations

from typing import Any

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
    assert isinstance(out.run_metadata.get("scoring_model_used", ""), str)
    assert len(str(out.run_metadata.get("scoring_prompt_hash", ""))) == 64
    assert len(str(out.run_metadata.get("scoring_score_hash", ""))) == 64
    assert len(out.scores) == 1
    payload = out.scores[0]
    assert payload["score_schema_version"] == "1.0.0"
    assert isinstance(payload["generated_at_utc"], str) and payload["generated_at_utc"]
    assert payload["final_label"] in {"duplicate_payment", "amount_anomaly"}
    assert 0.0 <= float(payload["confidence"]) <= 1.0
    assert isinstance(payload["model_used"], str) and payload["model_used"]
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
            "final_label": "made_up_type",
            "evidence_summary": "No test references",
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
        {
            "findings": findings,
            "hypotheses": [{"hypothesis_id": "H-1", "fraud_type": "duplicate_payment"}],
        },
    )
    assert validation["passed"] is False
    joined = "\n".join(validation["errors"])
    assert "source_test_ids no presentes en findings" in joined
    assert "suma" in joined
    assert "final_label fuera de fraud_type_probs" in joined
    assert "evidence_summary no referencia test_id real de findings" in joined


def test_rf15c_scoring_validator_accepts_valid_taxonomy_label_and_evidence_reference() -> None:
    valid_output = [
        {
            "ranking": [{"entity_key": "k=1"}],
            "final_label": "duplicate_payment",
            "evidence_summary": "Evidence from tests: TST-DUPLICATE-POSTINGS",
            "fraud_type_probs": [
                {
                    "fraud_type": "duplicate_payment",
                    "probability": 1.0,
                    "source_test_ids": ["TST-DUPLICATE-POSTINGS"],
                }
            ],
        }
    ]
    findings = [
        {"test_id": "TST-DUPLICATE-POSTINGS", "fraud_type": "duplicate_payment"},
    ]
    validation = _validate_scoring_evidence_and_probability_sum(
        valid_output,
        {"findings": findings, "hypotheses": [{"hypothesis_id": "H-1", "fraud_type": "duplicate_payment"}]},
    )
    assert validation["passed"] is True


def test_rf18_scoring_autocorrection_retries_and_recovers() -> None:
    state = create_initial_graph_state(run_id="rf18-05-repair")
    state.run_metadata["weights_config"] = "config/weights.yaml"
    state.run_metadata["scoring_top_k"] = 10
    state.run_metadata["scoring_simulate_invalid_once"] = True
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
                }
            ],
        }
    ]
    state.selected_tests = [{"hypothesis_id": "HYP-001", "test_id": "TST-DUPLICATE-POSTINGS"}]
    state.hypotheses = [{"hypothesis_id": "HYP-001", "fraud_type": "duplicate_payment"}]

    out = scoring_node(state)
    assert out.run_metadata["scoring_status"] == "OK"
    assert len(out.scores) == 1
    payload = out.scores[0]
    assert payload["final_label"] == "duplicate_payment"
    assert "TST-DUPLICATE-POSTINGS" in payload["evidence_summary"]
    prob_sum = sum(float(row.get("probability", 0.0) or 0.0) for row in payload["fraud_type_probs"])
    assert 0.999 <= prob_sum <= 1.001

    alpha_meta = out.run_metadata.get("alphacodium", {})
    scoring_meta = alpha_meta.get("scoring", {}) if isinstance(alpha_meta, dict) else {}
    assert int(scoring_meta.get("iterations", 0) or 0) >= 2


def test_rf18_scoring_node_uses_models_yaml_profile() -> None:
    state = create_initial_graph_state(run_id="rf18-06-model-profile")
    state.run_metadata["weights_config"] = "config/weights.yaml"
    state.run_metadata["models_config"] = "config/models.yaml"
    state.run_metadata["scoring_model_profile"] = "conservative"
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "test_version": "1.0.0",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 1,
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "duplicate_count"],
                    "metrics": {"duplicate_count": 2},
                }
            ],
        }
    ]
    out = scoring_node(state)
    payload = out.scores[0]
    assert payload["model_used"] == "scoring-stub-conservative-v1"
    assert out.run_metadata["scoring_model_profile"] == "conservative"


def test_rf18_scoring_no_findings_still_registers_hashes() -> None:
    state = create_initial_graph_state(run_id="rf18-07-empty-hashes")
    out = scoring_node(state)
    assert out.run_metadata["scoring_status"] == "NO_FINDINGS"
    assert len(str(out.run_metadata.get("scoring_prompt_hash", ""))) == 64
    assert len(str(out.run_metadata.get("scoring_score_hash", ""))) == 64


def test_rf18_scoring_generates_score_compare_for_two_profiles() -> None:
    state = create_initial_graph_state(run_id="rf18-08-compare")
    state.run_metadata["weights_config"] = "config/weights.yaml"
    state.run_metadata["models_config"] = "config/models.yaml"
    state.run_metadata["scoring_compare_profiles"] = ["default", "conservative"]
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

    out = scoring_node(state)
    assert out.run_metadata["scoring_compare_status"] == "OK"
    compare = out.run_metadata.get("score_compare", {})
    assert isinstance(compare, dict) and compare
    assert compare["baseline_profile"] == "default"
    assert compare["candidate_profile"] == "conservative"
    deltas = compare["deltas_by_fraud_type"]
    assert isinstance(deltas, list) and deltas

    experiment = out.run_metadata.get("scoring_experiment", {})
    assert isinstance(experiment, dict) and experiment
    assert experiment["status"] == "SKIPPED"
    assert experiment["reason"] in {"langsmith_not_configured", "missing_score_compare"}


def test_rf18_scoring_experiment_ready_when_langsmith_env_configured(monkeypatch: Any) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "dummy")
    monkeypatch.setenv("LANGSMITH_PROJECT", "erp-fraud-tests")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    monkeypatch.setenv("LANGSMITH_TRACE_LINK", "https://smith.langchain.com/o/test/r/123")

    state = create_initial_graph_state(run_id="rf18-09-ready")
    state.run_metadata["weights_config"] = "config/weights.yaml"
    state.run_metadata["models_config"] = "config/models.yaml"
    state.run_metadata["scoring_compare_profiles"] = ["default", "conservative"]
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "test_version": "1.0.0",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 1,
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "duplicate_count"],
                    "metrics": {"duplicate_count": 2},
                }
            ],
        }
    ]

    out = scoring_node(state)
    experiment = out.run_metadata.get("scoring_experiment", {})
    assert experiment["status"] == "READY"
    assert experiment["platform"] == "langsmith"
    assert len(str(experiment.get("score_compare_hash", ""))) == 64
