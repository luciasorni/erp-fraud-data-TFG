from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from src.erp_fraud.graph import (
    DEFAULT_GRAPH_SEQUENCE_FULL,
    DEFAULT_GRAPH_SEQUENCE_STUB,
    create_initial_graph_state,
    run_graph,
    run_graph_full,
)


def test_rf14_default_sequences_are_defined() -> None:
    assert DEFAULT_GRAPH_SEQUENCE_STUB == (
        "hypothesis_planner",
        "test_planner",
        "executor",
        "explainer",
        "scoring",
    )
    assert DEFAULT_GRAPH_SEQUENCE_FULL == (
        "ingest",
        "kb_index",
        "hypothesis_planner",
        "test_planner",
        "executor",
        "explainer",
        "scoring",
        "persist",
        "second_level_explainer",
    )


def test_rf14_run_graph_aborts_and_persists_when_precondition_fails(tmp_path: Path) -> None:
    state = create_initial_graph_state(run_id="rf14-11-abort")
    state.run_metadata["abort_graph"] = True
    state.run_metadata["persist_base_dir"] = str(tmp_path / "run_results")

    out = run_graph(initial_state=state, sequence=DEFAULT_GRAPH_SEQUENCE_FULL)

    assert out.run_metadata["graph_status"] == "ABORTED"
    assert out.run_metadata["graph_abort_reason"] == "precondition_failed_before_planning"
    manifest = Path(out.run_metadata["persist_manifest_path"])
    assert manifest.exists()


def test_rf14_run_graph_full_executes_with_stubbed_nodes(monkeypatch: Any, tmp_path: Path) -> None:
    import src.erp_fraud.graph.graph as graph_mod

    def _fake_run_node_by_id(*, node_id: str, state: Any) -> Any:
        status = state.run_metadata.setdefault("node_status", {})
        status[node_id] = "OK"
        if node_id == "persist":
            graph_dir = Path(tmp_path / "run_results" / state.run_id / "graph")
            graph_dir.mkdir(parents=True, exist_ok=True)
            manifest = graph_dir / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            state.run_metadata["persist_manifest_path"] = str(manifest)
        return state

    monkeypatch.setattr(graph_mod, "run_node_by_id", _fake_run_node_by_id)
    out = run_graph_full(
        run_id="rf14-11-full",
        run_metadata_overrides={"persist_base_dir": str(tmp_path / "run_results")},
    )
    assert out.run_metadata["graph_status"] == "OK"
    assert out.run_metadata["node_status"]["persist"] == "OK"
    assert Path(out.run_metadata["persist_manifest_path"]).exists()


def test_rf14_run_graph_retries_node_then_succeeds(monkeypatch: Any) -> None:
    import src.erp_fraud.graph.graph as graph_mod

    calls = {"executor": 0}

    def _fake_run_node_by_id(*, node_id: str, state: Any) -> Any:
        if node_id == "executor":
            calls["executor"] += 1
            if calls["executor"] == 1:
                raise RuntimeError("transient executor error")
        return state

    monkeypatch.setattr(graph_mod, "run_node_by_id", _fake_run_node_by_id)
    state = create_initial_graph_state(run_id="rf14-12-retry")
    state.run_metadata["graph_default_timeout_ms"] = 1000
    state.run_metadata["graph_node_retries"] = {"executor": 1}

    out = run_graph(initial_state=state, sequence=("executor",))
    assert out.run_metadata["graph_status"] == "OK"
    assert out.run_metadata["node_attempts"]["executor"] == 2
    assert out.run_metadata["node_status"]["executor"] == "OK"


def test_rf14_run_graph_timeout_marks_abort_and_runs_persist(monkeypatch: Any, tmp_path: Path) -> None:
    import src.erp_fraud.graph.graph as graph_mod

    def _fake_run_node_by_id(*, node_id: str, state: Any) -> Any:
        if node_id == "executor":
            time.sleep(0.05)
            return state
        if node_id == "persist":
            graph_dir = Path(tmp_path / "run_results" / state.run_id / "graph")
            graph_dir.mkdir(parents=True, exist_ok=True)
            manifest = graph_dir / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            state.run_metadata["persist_manifest_path"] = str(manifest)
        return state

    monkeypatch.setattr(graph_mod, "run_node_by_id", _fake_run_node_by_id)
    state = create_initial_graph_state(run_id="rf14-12-timeout")
    state.run_metadata["graph_default_timeout_ms"] = 10
    state.run_metadata["graph_default_retries"] = 0

    out = run_graph(initial_state=state, sequence=("executor", "persist"))
    assert out.run_metadata["graph_status"] == "ABORTED"
    assert "node_failed:executor:TimeoutError" in out.run_metadata["graph_abort_reason"]
    assert out.run_metadata["node_status"]["executor"] == "TIMEOUT"
    assert out.run_metadata["node_attempts"]["executor"] == 1
    assert Path(out.run_metadata["persist_manifest_path"]).exists()
