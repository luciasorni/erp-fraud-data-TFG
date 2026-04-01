from __future__ import annotations

from src.erp_fraud.catalog.scoring_agent import (
    ScoringAgent,
    load_models_config,
    resolve_scoring_model,
)


def test_rf18_scoring_agent_generates_score_schema_from_findings() -> None:
    agent = ScoringAgent(model_used="unit-test-model")
    payload = agent.generate(
        hypotheses=[{"hypothesis_id": "H-001", "fraud_type": "duplicate_payment"}],
        findings=[
            {"test_id": "T1", "fraud_type": "duplicate_payment", "finding_count": 3},
            {"test_id": "T2", "fraud_type": "amount_anomaly", "finding_count": 1},
        ],
        acfe_snippets=[{"chunk_id": "c1"}],
    )
    parsed = agent.parse_output(payload)

    assert parsed["score_schema_version"] == "1.0.0"
    assert parsed["final_label"] == "duplicate_payment"
    assert parsed["model_used"] == "unit-test-model"
    probs = parsed["fraud_type_probs"]
    assert len(probs) == 2
    assert abs(sum(float(row["probability"]) for row in probs) - 1.0) <= 1e-9


def test_rf18_scoring_agent_parse_rejects_missing_required_fields() -> None:
    agent = ScoringAgent()
    try:
        agent.parse_output({"final_label": "x"})
    except ValueError as exc:
        assert "faltan campos" in str(exc)
    else:
        raise AssertionError("Se esperaba ValueError por campos faltantes en ScoreSchema")


def test_rf18_models_config_resolves_profile() -> None:
    cfg = load_models_config("config/models.yaml")
    resolved = resolve_scoring_model(models_config=cfg, profile="conservative")
    assert resolved["profile"] == "conservative"
    assert resolved["model_used"] == "scoring-stub-conservative-v1"
