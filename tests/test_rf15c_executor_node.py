from __future__ import annotations

from pathlib import Path
from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, executor_node


def test_rf15c_executor_normalizes_findings_to_result_schema(monkeypatch: Any, tmp_path: Path) -> None:
    import src.erp_fraud.graph.nodes as nodes

    class _FakeRunner:
        def __init__(self, *, db_path: str, schema_name: str, table_name: str) -> None:
            _ = db_path, schema_name, table_name

        def run_all(
            self,
            selected_tests: list[str],
            *,
            catalog_path: str,
            validate_schema: bool,
            timeout_ms: int | None,
            run_id: str | None,
            log_path: Path | None,
        ) -> list[dict[str, Any]]:
            _ = selected_tests, catalog_path, validate_schema, timeout_ms, run_id, log_path
            return [
                {
                    "test_id": "TST-DUPLICATE-POSTINGS",
                    "status": "ok",
                    "finding_count": 1,
                    "rows": [{"entity_key": "x"}],
                }
            ]

    monkeypatch.setattr(nodes, "TestRunner", _FakeRunner)

    state = create_initial_graph_state(run_id="rf15c-07-executor")
    state.selected_tests = [{"hypothesis_id": "HYP-001", "test_id": "TST-DUPLICATE-POSTINGS"}]

    out = executor_node(state)
    assert len(out.findings) == 1
    finding = out.findings[0]
    assert finding["result_schema_version"] == "1.0.0"
    assert "generated_at_utc" in finding
    assert finding["status"] == "OK"
    assert isinstance(finding["columns"], list)
    assert isinstance(finding["metadata"], dict)
    assert len(out.test_runs) == 1
    assert out.test_runs[0]["test_id"] == "TST-DUPLICATE-POSTINGS"
    assert out.test_runs[0]["status"] == "OK"
