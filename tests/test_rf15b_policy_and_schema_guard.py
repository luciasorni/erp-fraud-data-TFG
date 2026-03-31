from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.erp_fraud.agents import (
    PolicyEnforcer,
    SchemaGuard,
    SchemaGuardValidationError,
    ToolPolicyDeniedError,
    build_params_hash,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_policy_enforcer_blocks_not_allowed_tool() -> None:
    enforcer = PolicyEnforcer.from_yaml(
        policy_path="config/agent_policies.yaml",
        tools_registry_path="config/tools_registry.yaml",
    )
    with pytest.raises(ToolPolicyDeniedError, match="no permitida"):
        enforcer.enforce_tool_call(agent_id="explainer", tool_id="DuckDBQuery")


def test_policy_enforcer_limits_calls_per_tool() -> None:
    enforcer = PolicyEnforcer.from_yaml(
        policy_path="config/agent_policies.yaml",
        tools_registry_path="config/tools_registry.yaml",
    )
    # scorer_classifier permite 2 llamadas a TestCatalog (ver config)
    enforcer.enforce_tool_call(agent_id="scorer_classifier", tool_id="TestCatalog")
    enforcer.enforce_tool_call(agent_id="scorer_classifier", tool_id="TestCatalog")
    with pytest.raises(ToolPolicyDeniedError, match="max_calls_per_tool"):
        enforcer.enforce_tool_call(agent_id="scorer_classifier", tool_id="TestCatalog")


def test_policy_enforcer_blocks_disabled_tool() -> None:
    enforcer = PolicyEnforcer.from_yaml(
        policy_path="config/agent_policies.yaml",
        tools_registry_path="config/tools_registry.yaml",
    )
    with pytest.raises(ToolPolicyDeniedError, match="deshabilitada"):
        enforcer.enforce_tool_call(agent_id="expert_recommender", tool_id="KBSearch")


def test_schema_guard_validates_existing_references(tmp_path: Path) -> None:
    schema_summary = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [
            {
                "table_schema": "main",
                "table_name": "fraud_1",
                "columns": [
                    {"name": "Kreditor", "type": "VARCHAR", "nullable": True, "ordinal_position": 1},
                    {"name": "Betrag", "type": "DOUBLE", "nullable": True, "ordinal_position": 2},
                ],
            }
        ],
    }
    schema_path = tmp_path / "schema_summary.json"
    _write_json(schema_path, schema_summary)

    guard = SchemaGuard.from_paths(
        schema_summary_path=schema_path,
        catalog_path="tests/catalog",
        validate_catalog_schema=True,
    )

    guard.validate_references(
        table_columns=[{"table": "main.fraud_1", "column": "Kreditor"}],
        test_ids=["TST-DUPLICATE-POSTINGS"],
    )


def test_schema_guard_detects_invalid_table_column_and_test_id(tmp_path: Path) -> None:
    schema_summary = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [
            {
                "table_schema": "main",
                "table_name": "fraud_1",
                "columns": [
                    {"name": "Kreditor", "type": "VARCHAR", "nullable": True, "ordinal_position": 1},
                ],
            }
        ],
    }
    schema_path = tmp_path / "schema_summary.json"
    _write_json(schema_path, schema_summary)

    guard = SchemaGuard.from_paths(
        schema_summary_path=schema_path,
        catalog_path="tests/catalog",
        validate_catalog_schema=True,
    )

    with pytest.raises(SchemaGuardValidationError, match="tabla no existe"):
        guard.validate_table("main.fraud_x")

    with pytest.raises(SchemaGuardValidationError, match="columna no existe"):
        guard.validate_column(table="main.fraud_1", column="Belegnummer")

    with pytest.raises(SchemaGuardValidationError, match="test_id no existe"):
        guard.validate_test_id("TST-UNKNOWN")


def test_policy_enforcer_logs_tool_calls_with_required_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "tool_calls.jsonl"
    enforcer = PolicyEnforcer.from_yaml(
        policy_path="config/agent_policies.yaml",
        tools_registry_path="config/tools_registry.yaml",
        tool_call_log_path=log_path,
    )

    out = enforcer.enforce_and_call(
        agent_id="test_executor",
        tool_id="TestCatalog",
        node_id="run_tests",
        tool_callable=lambda **kwargs: {"ok": True, "received": kwargs},
        test_id="TST-DUPLICATE-POSTINGS",
    )
    assert out["ok"] is True

    with pytest.raises(ToolPolicyDeniedError):
        enforcer.enforce_and_call(
            agent_id="explainer",
            tool_id="DuckDBQuery",
            node_id="explain",
            tool_callable=lambda **kwargs: {"ok": True},
            query_template_id="q_duplicate_postings_groups_v1",
            min_duplicate_count=1,
        )

    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    for row in rows:
        assert row["event"] == "tool_call"
        assert "tool_id" in row
        assert "agent_id" in row
        assert "params_hash" in row
        assert "duration_ms" in row
        assert "status" in row

    assert rows[0]["status"] == "OK"
    assert rows[1]["status"] == "DENIED"
    assert rows[0]["params_hash"] == build_params_hash({"test_id": "TST-DUPLICATE-POSTINGS"})
