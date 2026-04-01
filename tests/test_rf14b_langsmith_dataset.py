from __future__ import annotations

from pathlib import Path
from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, run_graph, run_graph_stub


def test_rf14b07_stub_run_writes_local_langsmith_eval_dataset() -> None:
    state = run_graph_stub(run_id="rf14b-07-local", dataset_hash="hash")
    payload = state.run_metadata.get("langsmith_eval_dataset", {})
    assert isinstance(payload, dict)
    assert payload.get("status") == "LOCAL_ONLY"
    path = Path(str(payload.get("path", "")))
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1


def test_rf14b07_publish_hook_runs_when_enabled(monkeypatch: Any) -> None:
    import src.erp_fraud.graph.graph as graph_mod

    def _fake_publish_langsmith_eval_dataset(*, state: Any, dataset_name: str, project_name: str) -> dict[str, Any]:
        return {
            "status": "OK",
            "reason": "",
            "dataset_name": dataset_name,
            "project_name": project_name,
            "dataset_id": "ds_test_123",
            "examples_count": 1,
        }

    monkeypatch.setattr(graph_mod, "publish_langsmith_eval_dataset", _fake_publish_langsmith_eval_dataset)

    state = create_initial_graph_state(run_id="rf14b-07-publish")
    state.run_metadata["enable_langsmith_dataset_publish"] = True
    state.run_metadata["langsmith_dataset_name"] = "erp-fraud-eval-tests"
    state.run_metadata["langsmith_project"] = "erp-fraud-tfg-tests"
    out = run_graph(initial_state=state, sequence=("hypothesis_planner", "test_planner", "executor", "explainer", "scoring"))

    payload = out.run_metadata.get("langsmith_eval_dataset", {})
    assert isinstance(payload, dict)
    assert payload.get("published") is True
    publish = payload.get("publish", {})
    assert isinstance(publish, dict)
    assert publish.get("status") == "OK"
    assert publish.get("dataset_name") == "erp-fraud-eval-tests"
