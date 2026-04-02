"""Helpers de tooling para nodos (sin dependencia de `_legacy`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import deps
from .common import resolve_project_path
from ...agents.policy_enforcer import PolicyEnforcer


def build_graph_policy_enforcer(state: Any) -> Any:
    run_id = str(state.run_id).strip() or "unknown_run"
    tool_log_path = str(
        state.run_metadata.get("graph_tool_log_path", f"run_results/{run_id}/graph_tool_calls.jsonl")
    ).strip()
    return PolicyEnforcer.from_yaml(
        policy_path=resolve_project_path("config/agent_policies.yaml"),
        tools_registry_path=resolve_project_path("config/tools_registry.yaml"),
        tool_call_log_path=resolve_project_path(tool_log_path),
    )


def tool_test_catalog(*, catalog_path: str) -> dict[str, Any]:
    return deps.tool_test_catalog(catalog_path=catalog_path)


def tool_schema(state: Any) -> dict[str, Any]:
    payload = state.schema if isinstance(state.schema, dict) else {}
    tables = payload.get("tables", []) if isinstance(payload.get("tables"), list) else []
    table_names = sorted(
        str(row.get("table_name", "")).strip()
        for row in tables
        if isinstance(row, dict) and str(row.get("table_name", "")).strip()
    )
    columns_by_table: dict[str, list[str]] = {}
    for row in tables:
        if not isinstance(row, dict):
            continue
        table_name = str(row.get("table_name", "")).strip()
        if not table_name:
            continue
        columns = row.get("columns", [])
        if not isinstance(columns, list):
            continue
        names = []
        for col in columns:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name", col.get("column_name", ""))).strip()
            if name:
                names.append(name)
        columns_by_table[table_name] = sorted(set(names))
    return {
        "source": "schema_summary",
        "payload": {
            "table_names": table_names,
            "count": len(table_names),
            "columns_by_table": columns_by_table,
        },
    }


def tool_data_catalog(*, data_dictionary_path: str) -> dict[str, Any]:
    path = Path(data_dictionary_path)
    if not path.exists():
        return {
            "source": "data_dictionary",
            "payload": {
                "entries": [],
                "count": 0,
                "status": "MISSING",
                "path": str(path),
            },
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "source": "data_dictionary",
            "payload": {
                "entries": [],
                "count": 0,
                "status": f"ERROR:{type(exc).__name__}",
                "path": str(path),
            },
        }

    entries = []
    if isinstance(raw, dict):
        maybe_entries = raw.get("entries", [])
        if isinstance(maybe_entries, list):
            entries = [row for row in maybe_entries if isinstance(row, dict)]
    slim_entries: list[dict[str, Any]] = []
    for row in entries:
        table = str(row.get("table", "")).strip()
        column = str(row.get("column", "")).strip()
        if not table or not column:
            continue
        slim_entries.append({"table": table, "column": column, "type": str(row.get("type", "")).strip()})
    return {
        "source": "data_dictionary",
        "payload": {
            "entries": slim_entries,
            "count": len(slim_entries),
            "status": "OK",
            "path": str(path),
        },
    }


def tool_runstore_write_stub(*, run_id: str, hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "operation": "write",
        "status": "OK",
        "path": f"run_results/{run_id}/hypotheses.json",
        "count": len(hypotheses),
    }
