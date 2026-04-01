from __future__ import annotations

from pathlib import Path
from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, hypothesis_planner_node


def test_rf14_hypothesis_planner_uses_policy_tools_and_populates_context(tmp_path: Path) -> None:
    state = create_initial_graph_state(run_id="rf14-05-tools")
    state.schema = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [{"table_name": "fraud_1", "columns": [{"name": "Kreditor"}]}],
    }
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["graph_tool_log_path"] = str(tmp_path / "graph_tool_calls.jsonl")
    state.run_metadata["kb_search_enabled"] = False

    out = hypothesis_planner_node(state)

    assert len(out.hypotheses) == 1
    tool_context = out.hypotheses[0]["tool_context"]
    assert tool_context["catalog_tests_count"] >= 1
    assert tool_context["schema_tables_count"] == 1
    assert tool_context["kb_search_status"] == "SKIPPED"
    assert out.run_metadata["hypothesis_runstore_status"] in {"OK", "DENIED"}

    tool_log_path = Path(out.run_metadata["graph_tool_log_path"])
    assert tool_log_path.exists()
    log_text = tool_log_path.read_text(encoding="utf-8")
    assert "TestCatalog" in log_text
    assert "Schema" in log_text
    assert "RunStore" in log_text


def test_rf14_hypothesis_planner_kb_enabled_uses_kb_tool(monkeypatch: Any, tmp_path: Path) -> None:
    import src.erp_fraud.graph.nodes as nodes

    class _FakeKBSearchTool:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def search(self, *, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> dict[str, Any]:
            _ = top_k, filters
            return {"query": query, "count": 2, "hits": [{"chunk_id": "c1"}, {"chunk_id": "c2"}]}

    monkeypatch.setattr(nodes, "KBSearchTool", _FakeKBSearchTool)

    state = create_initial_graph_state(run_id="rf14-05-kb")
    state.schema = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [{"table_name": "fraud_1", "columns": [{"name": "Kreditor"}]}],
    }
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["graph_tool_log_path"] = str(tmp_path / "graph_tool_calls_kb.jsonl")
    state.run_metadata["kb_search_enabled"] = True
    state.run_metadata["base_dir"] = str(tmp_path)

    out = hypothesis_planner_node(state)
    tool_context = out.hypotheses[0]["tool_context"]
    assert tool_context["kb_search_status"] == "OK"
    assert tool_context["kb_hits_count"] == 2

