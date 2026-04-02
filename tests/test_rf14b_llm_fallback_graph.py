from __future__ import annotations

from typing import Any

from src.erp_fraud.graph import run_graph_stub


def test_rf14b_llm_node_failures_do_not_abort_graph(monkeypatch: Any) -> None:
    import src.erp_fraud.graph.nodes.explainer as explainer_mod
    import src.erp_fraud.graph.nodes.planning as planning_mod

    def _raise_alpha_loop(**_kwargs: Any) -> Any:
        raise RuntimeError("forced_alpha_loop_failure")

    monkeypatch.setattr(planning_mod, "_run_alpha_loop_for_node", _raise_alpha_loop)
    monkeypatch.setattr(explainer_mod, "_run_alpha_loop_for_node", _raise_alpha_loop)

    state = run_graph_stub(run_id="rf14b-llm-fallback", dataset_hash="hash")
    assert state.run_metadata.get("graph_status") == "OK"
    assert state.run_metadata.get("hypothesis_fallback_used") is True
    assert state.run_metadata.get("test_planner_fallback_used") is True
    assert state.run_metadata.get("explainer_fallback_used") is True
