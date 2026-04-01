from __future__ import annotations

from src.erp_fraud.graph import DEFAULT_GRAPH_SEQUENCE, run_graph_stub


def test_rf14_stub_sequence_is_expected() -> None:
    assert DEFAULT_GRAPH_SEQUENCE == (
        "hypothesis_planner",
        "test_planner",
        "executor",
        "explainer",
        "scoring",
    )


def test_rf14_run_graph_stub_updates_state_and_node_status() -> None:
    state = run_graph_stub(run_id="rf14-02-stub", dataset_hash="hash-rf14")
    node_status = state.run_metadata.get("node_status", {})
    assert isinstance(node_status, dict)
    for node_id in DEFAULT_GRAPH_SEQUENCE:
        assert node_status.get(node_id) == "OK"

    assert len(state.hypotheses) >= 1
    assert len(state.selected_tests) >= 1
    assert len(state.findings) >= 1
    assert len(state.explanations) >= 1
    assert len(state.scores) >= 1

    trace_events = state.run_metadata.get("node_trace_events", [])
    assert isinstance(trace_events, list)
    assert len(trace_events) >= len(DEFAULT_GRAPH_SEQUENCE) * 2
    assert any(
        isinstance(row, dict)
        and row.get("node_id") == "hypothesis_planner"
        and row.get("stage") == "start"
        for row in trace_events
    )
    assert any(
        isinstance(row, dict)
        and row.get("node_id") == "scoring"
        and row.get("stage") == "end"
        and row.get("status") == "OK"
        for row in trace_events
    )

    langsmith = state.run_metadata.get("langsmith", {})
    assert isinstance(langsmith, dict)
    assert "configured" in langsmith
