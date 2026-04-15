from __future__ import annotations

from pathlib import Path
from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, kb_index_node


def test_rf14_kb_index_node_disabled_does_not_build(monkeypatch: Any) -> None:
    called = {"value": False}

    def _fake_build_kb_index(**_kwargs: Any) -> dict[str, Any]:
        called["value"] = True
        return {}

    import src.erp_fraud.graph.nodes as nodes

    monkeypatch.setattr(nodes, "build_kb_index", _fake_build_kb_index)
    state = create_initial_graph_state(run_id="rf14-04-disabled")
    state.run_metadata["kb_index_enabled"] = False

    out = kb_index_node(state)

    assert called["value"] is False
    assert out.kb_status["status"] == "DISABLED"
    assert out.run_metadata["kb_index_status"] == "DISABLED"


def test_rf14_kb_index_node_ok_updates_state(monkeypatch: Any, tmp_path: Path) -> None:
    manifest_path = tmp_path / "index_manifest.json"
    state_path = tmp_path / "index_state.json"

    def _fake_build_kb_index(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["incremental_rebuild"] is True
        return {
            "chunks_indexed": 7,
            "sources_used": [{"source_id": "doc1"}, {"source_id": "doc2"}],
            "persist_dir": str(tmp_path / "kb" / "chroma"),
        }

    import src.erp_fraud.graph.nodes as nodes

    monkeypatch.setattr(nodes, "build_kb_index", _fake_build_kb_index)
    state = create_initial_graph_state(run_id="rf14-04-ok")
    state.run_metadata["base_dir"] = str(tmp_path)
    state.run_metadata["kb_index_enabled"] = True
    state.run_metadata["kb_manifest_path"] = str(manifest_path)
    state.run_metadata["kb_index_state_path"] = str(state_path)

    out = kb_index_node(state)

    assert out.kb_status["status"] == "OK"
    assert out.kb_status["chunks_indexed"] == 7
    assert out.kb_status["sources_used"] == 2
    assert out.kb_status["index_manifest_path"] == str(manifest_path)
    assert out.run_metadata["kb_index_status"] == "OK"
    assert out.run_metadata["kb_index_manifest_path"] == str(manifest_path)
    assert out.run_metadata["kb_index_state_path"] == str(state_path)
