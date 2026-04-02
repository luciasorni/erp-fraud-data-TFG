from __future__ import annotations

from typing import Any

from src.erp_fraud.graph import run_graph_stub


def test_rf14b_langsmith_runs_metadata_is_attached(monkeypatch: Any) -> None:
    import src.erp_fraud.graph.graph as graph_mod

    def _fake_publish_langsmith_node_runs(*, state: Any) -> dict[str, Any]:
        _ = state
        return {
            "status": "OK",
            "project": "erp-fraud-tfg",
            "runs_published": 5,
            "trace_link": "https://api.smith.langchain.com/o/erp-fraud-tfg",
        }

    monkeypatch.setattr(graph_mod, "publish_langsmith_node_runs", _fake_publish_langsmith_node_runs)
    out = run_graph_stub(run_id="rf14b-langsmith-runs", dataset_hash="hash")
    meta = out.run_metadata
    assert meta.get("langsmith_runs", {}).get("status") == "OK"
    assert str(meta.get("langsmith_trace_link", "")).startswith("https://")
