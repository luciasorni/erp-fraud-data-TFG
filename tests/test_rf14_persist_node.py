from __future__ import annotations

import json
from pathlib import Path

from src.erp_fraud.graph import create_initial_graph_state, persist_node


def test_rf14_persist_node_writes_graph_artifacts(tmp_path: Path) -> None:
    state = create_initial_graph_state(run_id="rf14-10-persist")
    state.run_metadata["persist_base_dir"] = str(tmp_path / "run_results")
    state.hypotheses = [{"hypothesis_id": "HYP-001"}]
    state.selected_tests = [{"hypothesis_id": "HYP-001", "test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT"}]
    state.findings = [{"test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT", "finding_count": 1}]
    state.explanations = [{"test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT", "summary": "ok"}]
    state.scores = [{"summary": {"entities_scored": 1}, "ranking": []}]

    out = persist_node(state)

    graph_dir = Path(out.run_metadata["persist_graph_dir"])
    assert graph_dir.exists()

    expected_files = [
        graph_dir / "hypotheses.json",
        graph_dir / "selected_tests.json",
        graph_dir / "findings.json",
        graph_dir / "explanations.json",
        graph_dir / "scores.json",
        graph_dir / "graph_state.json",
        graph_dir / "manifest.json",
    ]
    for path in expected_files:
        assert path.exists(), f"Missing artifact: {path}"

    manifest = json.loads((graph_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "rf14-10-persist"
    assert "scores_json" in manifest["artifacts"]
    assert out.run_metadata["persist_status"] == "OK"

