from __future__ import annotations

import json
from pathlib import Path

from src.erp_fraud.graph import create_initial_graph_state, persist_node, scoring_node


def test_rf18_end_to_end_scoring_compare_and_persist_artifacts(tmp_path: Path) -> None:
    state = create_initial_graph_state(run_id="rf18-e2e")
    state.run_metadata["persist_base_dir"] = str(tmp_path / "run_results")
    state.run_metadata["weights_config"] = "config/weights.yaml"
    state.run_metadata["models_config"] = "config/models.yaml"
    state.run_metadata["scoring_model_profile"] = "default"
    state.run_metadata["scoring_compare_profiles"] = ["default", "conservative"]
    state.hypotheses = [{"hypothesis_id": "HYP-001", "fraud_type": "duplicate_payment"}]
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

    scored = scoring_node(state)
    assert scored.run_metadata["scoring_status"] == "OK"
    assert len(str(scored.run_metadata.get("scoring_prompt_hash", ""))) == 64
    assert len(str(scored.run_metadata.get("scoring_score_hash", ""))) == 64
    assert scored.run_metadata.get("scoring_compare_status") == "OK"

    out = persist_node(scored)
    graph_dir = Path(out.run_metadata["persist_graph_dir"])
    assert (graph_dir / "scores.json").exists()
    assert (graph_dir / "score_compare.json").exists()
    assert (graph_dir / "score_experiment.json").exists()

    manifest = json.loads((graph_dir / "manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", {})
    assert "scores_json" in artifacts
    assert "score_compare_json" in artifacts
    assert "score_experiment_json" in artifacts
