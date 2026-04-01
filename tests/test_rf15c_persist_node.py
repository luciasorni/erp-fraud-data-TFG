from __future__ import annotations

import json
from pathlib import Path

from src.erp_fraud.graph import create_initial_graph_state, persist_node


def test_rf15c_persist_node_writes_rf15c_artifacts() -> None:
    state = create_initial_graph_state(run_id="rf15c-12-persist")
    state.hypotheses = [{"hypothesis_id": "HYP-001", "title": "x"}]
    state.selected_tests = [{"hypothesis_id": "HYP-001", "test_id": "TST-DUPLICATE-POSTINGS"}]
    state.explanations = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "status": "OK",
            "fraud_type": "duplicate_payment",
            "finding_count": 1,
            "cited_keys": {"kreditor": "V1"},
            "cited_evidence_columns": ["kreditor", "betrag"],
            "summary": "ok",
            "acfe_reference": {"status": "SKIPPED", "hits": []},
        }
    ]
    state.scores = [{"fraud_type_probs": [{"fraud_type": "duplicate_payment", "probability": 1.0}]}]
    state.run_metadata["score_compare"] = {
        "version": "1.0.0",
        "baseline_profile": "default",
        "candidate_profile": "conservative",
        "deltas_by_fraud_type": [
            {
                "fraud_type": "duplicate_payment",
                "baseline_probability": 1.0,
                "candidate_probability": 1.0,
                "delta_probability": 0.0,
            }
        ],
    }
    state.run_metadata["scoring_experiment"] = {
        "status": "SKIPPED",
        "reason": "langsmith_not_configured",
        "platform": "langsmith",
    }

    out = persist_node(state)
    graph_dir = Path(out.run_metadata["persist_graph_dir"])
    assert (graph_dir / "hypotheses.json").exists()
    assert (graph_dir / "selected_tests.json").exists()
    assert (graph_dir / "explanation.json").exists()
    assert (graph_dir / "explanations.json").exists()
    assert (graph_dir / "explanation.md").exists()
    assert (graph_dir / "explanations.md").exists()
    assert (graph_dir / "score.json").exists()
    assert (graph_dir / "score_compare.json").exists()
    assert (graph_dir / "score_experiment.json").exists()

    md = (graph_dir / "explanations.md").read_text(encoding="utf-8")
    assert "TST-DUPLICATE-POSTINGS" in md
    assert "cited_evidence_columns" in md

    manifest = json.loads((graph_dir / "manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    assert "score_json" in artifacts
    assert "score_compare_json" in artifacts
    assert "score_experiment_json" in artifacts
    assert "explanation_json" in artifacts
    assert "explanation_md" in artifacts
    assert "explanations_md" in artifacts
