from __future__ import annotations

from pathlib import Path
from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, executor_node


def test_rf14_executor_node_runs_selected_tests(monkeypatch: Any, tmp_path: Path) -> None:
    import src.erp_fraud.graph.nodes as nodes

    calls: dict[str, Any] = {}

    class _FakeRunner:
        def __init__(self, *, db_path: str, schema_name: str, table_name: str) -> None:
            calls["init"] = {
                "db_path": db_path,
                "schema_name": schema_name,
                "table_name": table_name,
            }

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
            calls["run_all"] = {
                "selected_tests": selected_tests,
                "catalog_path": catalog_path,
                "validate_schema": validate_schema,
                "timeout_ms": timeout_ms,
                "run_id": run_id,
                "log_path": str(log_path) if log_path is not None else "",
            }
            return [
                {
                    "test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT",
                    "status": "OK",
                    "finding_count": 2,
                    "rows": [{"entity_key": "k=1"}],
                }
            ]

    monkeypatch.setattr(nodes, "TestRunner", _FakeRunner)

    state = create_initial_graph_state(run_id="rf14-07-exec")
    state.run_metadata["db_path"] = "erp.duckdb"
    state.run_metadata["schema_name"] = "main"
    state.run_metadata["table_name"] = "fraud_1"
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["executor_timeout_ms"] = 1500
    state.run_metadata["executor_test_runner_log_path"] = str(tmp_path / "exec_logs.jsonl")
    state.selected_tests = [
        {"hypothesis_id": "HYP-001", "test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT"},
        {"hypothesis_id": "HYP-001", "test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT"},
    ]

    out = executor_node(state)

    assert calls["init"]["db_path"] == "erp.duckdb"
    assert calls["run_all"]["selected_tests"] == ["TST-SPLIT-PAYMENTS-NEAR-LIMIT"]
    assert calls["run_all"]["validate_schema"] is True
    assert calls["run_all"]["timeout_ms"] == 1500
    assert out.run_metadata["executor_status"] == "OK"
    assert out.run_metadata["executor_tests_count"] == 1
    assert out.run_metadata["executor_findings_total"] == 2
    assert len(out.findings) == 1


def test_rf14_executor_node_skips_when_no_selected_tests() -> None:
    state = create_initial_graph_state(run_id="rf14-07-empty")
    state.selected_tests = []

    out = executor_node(state)

    assert out.findings == []
    assert out.run_metadata["executor_status"] == "SKIPPED_NO_SELECTED_TESTS"
    assert out.run_metadata["executor_tests_count"] == 0
    assert out.run_metadata["executor_findings_total"] == 0

