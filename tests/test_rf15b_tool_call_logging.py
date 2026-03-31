from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.erp_fraud.agents import PolicyEnforcer, ToolCallLogger, build_params_hash


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_params_hash_is_stable() -> None:
    h1 = build_params_hash({"b": 2, "a": 1})
    h2 = build_params_hash({"a": 1, "b": 2})
    assert h1 == h2


def test_tool_call_logger_writes_required_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "tool_calls.jsonl"
    logger = ToolCallLogger(log_path)

    rec = logger.log_tool_call(
        tool_id="TestCatalog",
        agent_id="test_executor",
        node_id="run_tests",
        params={"test_id": "TST-DUPLICATE-POSTINGS"},
        status="OK",
        duration_ms=12,
    )
    assert rec["event"] == "tool_call"
    assert rec["status"] == "OK"

    rows = _read_jsonl(log_path)
    assert len(rows) == 1
    assert sorted(rows[0].keys()) == [
        "agent_id",
        "duration_ms",
        "event",
        "node_id",
        "params_hash",
        "status",
        "timestamp_utc",
        "tool_id",
    ]


def test_policy_enforcer_logs_error_status_when_tool_callable_fails(tmp_path: Path) -> None:
    log_path = tmp_path / "tool_calls.jsonl"
    enforcer = PolicyEnforcer.from_yaml(
        policy_path="config/agent_policies.yaml",
        tools_registry_path="config/tools_registry.yaml",
        tool_call_log_path=log_path,
    )

    with pytest.raises(RuntimeError, match="boom"):
        enforcer.enforce_and_call(
            agent_id="test_executor",
            node_id="run_tests",
            tool_id="TestCatalog",
            tool_callable=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
            test_id="TST-DUPLICATE-POSTINGS",
        )

    rows = _read_jsonl(log_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "ERROR"
    assert rows[0]["tool_id"] == "TestCatalog"
    assert "error_summary" in rows[0]
