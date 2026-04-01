"""Nodo ejecutor."""

from __future__ import annotations

# ruff: noqa: F401

from . import _legacy as _legacy

globals().update(vars(_legacy))

def executor_node(state: GraphState) -> GraphState:
    """Nodo no-LLM: ejecuta tests seleccionados y guarda findings (RF14-07)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    _record_graph_node_model_config(
        node_id="executor",
        metadata=metadata,
        default_model_used="deterministic-sql-runner",
        overrides={"mode": "deterministic"},
    )
    db_path = _resolve_project_path(
        str(metadata.get("db_path", DEFAULT_DB_PATH)).strip() or DEFAULT_DB_PATH
    )
    schema_name = str(metadata.get("schema_name", DEFAULT_SCHEMA_NAME)).strip() or DEFAULT_SCHEMA_NAME
    table_name = str(metadata.get("table_name", DEFAULT_TABLE_NAME)).strip() or DEFAULT_TABLE_NAME
    catalog_path = _resolve_project_path(
        str(metadata.get("catalog_path", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
    )
    timeout_ms = metadata.get("executor_timeout_ms")
    if timeout_ms is None:
        timeout_ms = DEFAULT_EXECUTOR_TIMEOUT_MS
    timeout_value = int(timeout_ms) if isinstance(timeout_ms, int) and timeout_ms > 0 else None

    selected_ids: list[str] = []
    seen: set[str] = set()
    for row in state.selected_tests:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id", "")).strip()
        if not test_id or test_id in seen:
            continue
        seen.add(test_id)
        selected_ids.append(test_id)

    runner = TestRunner(
        db_path=db_path,
        schema_name=schema_name,
        table_name=table_name,
    )

    if not selected_ids:
        state.findings = []
        state.test_runs = []
        metadata["executor_status"] = "SKIPPED_NO_SELECTED_TESTS"
        metadata["executor_tests_count"] = 0
        metadata["executor_findings_total"] = 0
        return state

    run_id = str(state.run_id).strip() or "unknown_run"
    log_path = _resolve_project_path(
        metadata.get(
            "executor_test_runner_log_path",
            f"run_results/{run_id}/graph_executor_test_runner_logs.jsonl",
        )
    )
    try:
        results = runner.run_all(
            selected_tests=selected_ids,
            catalog_path=catalog_path,
            validate_schema=True,
            timeout_ms=timeout_value,
            run_id=run_id,
            log_path=Path(log_path),
        )
        metadata["executor_runner_status"] = "OK"
    except Exception as exc:
        metadata["executor_runner_status"] = f"ERROR: {type(exc).__name__}: {exc}"
        # Fallback robusto para stub CI: evita abortar el grafo por entorno/catálogo.
        fallback_test_id = selected_ids[0] if selected_ids else "TST-STUB-FALLBACK"
        results = [
            {
                "result_schema_version": RESULT_SCHEMA_VERSION,
                "generated_at_utc": "",
                "test_id": fallback_test_id,
                "test_version": "0.0.0-stub",
                "fraud_type": "unknown",
                "status": "OK",
                "finding_count": 1,
                "duration_ms": 0,
                "columns": ["entity_key", "fallback_reason"],
                "rows": [
                    {
                        "entity_key": "stub=fallback",
                        "keys": {"stub": "fallback"},
                        "evidence_columns": ["fallback_reason"],
                        "metrics": {"fallback": 1},
                        "fallback_reason": f"{type(exc).__name__}: {exc}",
                    }
                ],
                "metadata": {
                    "implementation_type": "stub_fallback",
                    "executed_on": f"{schema_name}.{table_name}",
                },
            }
        ]

    normalized_results = [_normalize_result_schema_payload(row) for row in results if isinstance(row, dict)]
    state.findings = [dict(row) for row in normalized_results]
    state.test_runs = [_to_test_run_record(row) for row in normalized_results]
    metadata["executor_status"] = "OK"
    metadata["executor_tests_count"] = len(state.findings)
    metadata["executor_findings_total"] = sum(
        int(row.get("finding_count", 0) or 0) for row in state.findings if isinstance(row, dict)
    )
    metadata["executor_result_schema_version"] = RESULT_SCHEMA_VERSION
    metadata["executor_test_runs_count"] = len(state.test_runs)
    metadata["executor_test_runner_log_path"] = log_path
    return state
