from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, hypothesis_planner_node
from src.erp_fraud.graph.nodes import _validate_hypotheses_output


def _write_data_dictionary(path: Path) -> None:
    payload = {
        "entries": [
            {"table": "fraud_1", "column": "Kreditor", "type": "VARCHAR"},
            {"table": "fraud_1", "column": "Belegnummer", "type": "VARCHAR"},
            {"table": "fraud_1", "column": "Betrag", "type": "DOUBLE"},
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_rf15c_hypothesis_planner_includes_sources_from_catalog_schema_and_data_catalog(
    tmp_path: Path,
) -> None:
    data_dictionary_path = tmp_path / "data_dictionary.json"
    _write_data_dictionary(data_dictionary_path)

    state = create_initial_graph_state(run_id="rf15c-03-sources")
    state.schema = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [{"table_name": "fraud_1", "columns": [{"name": "Kreditor"}]}],
    }
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["data_dictionary_path"] = str(data_dictionary_path)
    state.run_metadata["kb_search_enabled"] = False

    out = hypothesis_planner_node(state)
    assert out.hypotheses
    hyp = out.hypotheses[0]
    assert "sources" in hyp
    assert isinstance(hyp.get("fraud_type"), str) and hyp["fraud_type"]
    assert isinstance(hyp.get("process_step"), str) and hyp["process_step"]
    assert isinstance(hyp.get("evidence_requirements"), list)
    source_types = {row.get("type") for row in hyp["sources"] if isinstance(row, dict)}
    assert "test_catalog" in source_types
    assert "schema_summary" in source_types
    assert "data_catalog" in source_types

    tool_context = hyp["tool_context"]
    assert int(tool_context["data_catalog_fields_count"]) == 3
    assert int(tool_context["schema_tables_count"]) == 1
    assert int(tool_context["catalog_tests_count"]) >= 1
    for req in hyp["evidence_requirements"]:
        assert req["table"] == "fraud_1"
        assert req["column"] in {"Kreditor", "Belegnummer", "Betrag"}
    assert isinstance(hyp.get("fraud_tree_branch"), str) and hyp["fraud_tree_branch"]
    assert isinstance(hyp.get("fraud_tree_branch_label"), str) and hyp["fraud_tree_branch_label"]
    assert str(hyp.get("fraud_tree_source_document", "")).endswith("docs/external/fraud_type.pdf")


def test_rf15c_hypothesis_planner_kb_sources_are_attached_when_enabled(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import src.erp_fraud.graph.nodes as nodes

    class _FakeKBSearchTool:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def search(self, *, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> dict[str, Any]:
            _ = top_k, filters
            return {
                "query": query,
                "count": 2,
                "hits": [
                    {"chunk_id": "chunk-a", "metadata": {"source_path": "docs/external/a.pdf"}},
                    {"chunk_id": "chunk-b", "metadata": {"source_path": "docs/external/b.pdf"}},
                ],
            }

    monkeypatch.setattr(nodes, "KBSearchTool", _FakeKBSearchTool)

    data_dictionary_path = tmp_path / "data_dictionary.json"
    _write_data_dictionary(data_dictionary_path)

    state = create_initial_graph_state(run_id="rf15c-03-kb")
    state.schema = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [{"table_name": "fraud_1", "columns": [{"name": "Kreditor"}]}],
    }
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["data_dictionary_path"] = str(data_dictionary_path)
    state.run_metadata["kb_search_enabled"] = True
    state.run_metadata["base_dir"] = str(tmp_path)
    state.run_metadata["hypothesis_kb_top_k"] = 2
    state.run_metadata["hypothesis_query"] = "split payments near threshold"

    out = hypothesis_planner_node(state)
    hyp = out.hypotheses[0]
    kb_sources = [
        row for row in hyp["sources"] if isinstance(row, dict) and str(row.get("type", "")) == "kb_search"
    ]
    assert len(kb_sources) == 1
    assert kb_sources[0]["query"] == "split payments near threshold"
    assert kb_sources[0]["top_k"] == 2
    assert kb_sources[0]["hits_count"] == 2
    assert kb_sources[0]["chunk_ids"] == ["chunk-a", "chunk-b"]


def test_rf15c_hypothesis_validation_rejects_invalid_fraud_type_process_and_evidence() -> None:
    output = [
        {
            "hypothesis_id": "HYP-001",
            "title": "Bad hypothesis",
            "fraud_type": "not_allowed",
            "process_step": "bad_step",
            "evidence_requirements": [{"table": "fraud_1", "column": "MissingColumn"}],
            "sources": [{"type": "test_catalog"}, {"type": "schema_summary"}],
        }
    ]
    validation = _validate_hypotheses_output(
        output,
        {
            "allowed_fraud_types": ["duplicate_payment"],
            "allowed_process_steps": ["invoice_posting"],
            "schema_columns_by_table": {"fraud_1": ["Kreditor", "Betrag"]},
        },
    )
    assert validation["passed"] is False
    joined = "\n".join(validation["errors"])
    assert "fraud_type fuera de catálogo" in joined
    assert "process_step fuera de catálogo" in joined
    assert "columna no existente" in joined
