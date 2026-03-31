from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
import yaml

from src.erp_fraud.agents import (
    QueryTemplateNotAllowedError,
    QueryTemplateValidationError,
    execute_query_template,
    load_query_templates_config,
)


def _build_inmemory_conn_with_fraud_table() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE fraud_1 (
            Kreditor VARCHAR,
            Belegnummer VARCHAR,
            Position VARCHAR,
            Betrag DOUBLE,
            Transaktionsart VARCHAR
        )
        """
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?)",
        [
            ("V1", "D1", "10", 100.0, "N"),
            ("V1", "D1", "10", 100.0, "N"),
            ("V2", "D2", "20", 150.0, "N"),
            ("V2", "D3", "30", 75.0, "A"),
        ],
    )
    return conn


def test_tools_registry_has_all_rf15b_tools() -> None:
    payload = yaml.safe_load(Path("config/tools_registry.yaml").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    tools = payload.get("tools")
    assert isinstance(tools, dict)

    expected = {"DuckDBQuery", "Schema", "TestCatalog", "KBSearch", "RunStore"}
    assert expected.issubset(set(tools.keys()))

    for tool_id in expected:
        tool_spec = tools[tool_id]
        assert isinstance(tool_spec, dict)
        assert tool_spec.get("tool_id") == tool_id
        assert isinstance(tool_spec.get("inputs"), dict)
        assert isinstance(tool_spec.get("outputs"), dict)
        assert isinstance(tool_spec.get("limits"), dict)


def test_load_query_templates_config_reads_allowlist() -> None:
    cfg = load_query_templates_config("config/query_templates.yaml")
    templates = cfg.get("templates")
    assert isinstance(templates, dict)
    assert "q_duplicate_postings_groups_v1" in templates
    assert "q_vendor_amount_above_v1" in templates


def test_execute_query_template_returns_expected_output_schema() -> None:
    conn = _build_inmemory_conn_with_fraud_table()
    try:
        out = execute_query_template(
            query_template_id="q_duplicate_postings_groups_v1",
            params={"min_duplicate_count": 1},
            conn=conn,
        )
    finally:
        conn.close()

    assert sorted(out.keys()) == ["columns", "query_template_id", "row_count", "rows"]
    assert out["query_template_id"] == "q_duplicate_postings_groups_v1"
    assert out["row_count"] == 1
    assert out["columns"] == ["kreditor", "belegnummer", "position", "betrag", "duplicate_count"]
    assert out["rows"][0]["duplicate_count"] == 2


def test_execute_query_template_rejects_unknown_template_id() -> None:
    conn = _build_inmemory_conn_with_fraud_table()
    try:
        with pytest.raises(QueryTemplateNotAllowedError, match="allowlist"):
            execute_query_template(
                query_template_id="q_unknown_template",
                params={},
                conn=conn,
            )
    finally:
        conn.close()


def test_execute_query_template_rejects_missing_or_extra_params() -> None:
    conn = _build_inmemory_conn_with_fraud_table()
    try:
        with pytest.raises(QueryTemplateValidationError, match="faltan parámetros"):
            execute_query_template(
                query_template_id="q_vendor_amount_above_v1",
                params={"kreditor": "V1"},
                conn=conn,
            )
        with pytest.raises(QueryTemplateValidationError, match="no permitidos"):
            execute_query_template(
                query_template_id="q_vendor_amount_above_v1",
                params={
                    "kreditor": "V1",
                    "min_amount": 90.0,
                    "sql": "select 1",
                },
                conn=conn,
            )
    finally:
        conn.close()
