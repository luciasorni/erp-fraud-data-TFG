from __future__ import annotations

import json
from pathlib import Path

import duckdb

from src.erp_fraud.graph import run_graph_full
from src.erp_fraud.storage.schema_summary import write_schema_summary_json


def _prepare_o2c_graph_db(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute('CREATE SCHEMA IF NOT EXISTS "o2c"')
        conn.execute(
            '''
            CREATE TABLE "o2c"."o2c_order" (
              sales_order_id VARCHAR,
              sales_order_item_id VARCHAR,
              customer_id VARCHAR,
              net_amount DOUBLE,
              condition_amount DOUBLE,
              ordered_quantity DOUBLE
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE "o2c"."o2c_delivery" (
              delivery_id VARCHAR,
              delivery_item_id VARCHAR,
              reference_sales_order_id VARCHAR,
              reference_sales_order_item_id VARCHAR,
              delivered_quantity DOUBLE
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE "o2c"."o2c_collection" (
              company_code VARCHAR,
              receivable_document_id VARCHAR,
              fiscal_year VARCHAR,
              customer_id VARCHAR,
              amount_local_currency DOUBLE,
              baseline_date DATE,
              clearing_date DATE,
              clearing_document_id VARCHAR
            )
            '''
        )

        conn.executemany(
            'INSERT INTO "o2c"."o2c_order" VALUES (?, ?, ?, ?, ?, ?)',
            [
                ("5000000001", "000010", "V01", 100.0, -5.0, 10.0),
                ("5000000002", "000010", "V01", 105.0, -5.0, 10.0),
                ("5000000003", "000010", "V01", 98.0, -5.0, 10.0),
                ("5000000004", "000010", "V01", 500.0, -250.0, 10.0),
            ],
        )
        conn.executemany(
            'INSERT INTO "o2c"."o2c_delivery" VALUES (?, ?, ?, ?, ?)',
            [("8000000001", "000010", "5000000001", "000010", 15.0)],
        )
        conn.executemany(
            'INSERT INTO "o2c"."o2c_collection" VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [("1000", "1900000010", "2026", "V01", 20000.0, "2026-01-20", "2026-01-10", None)],
        )
    finally:
        conn.close()


def test_rf11_o2c_graph_full_runs_with_o2c_catalog(tmp_path: Path) -> None:
    db_path = tmp_path / "o2c_graph.duckdb"
    _prepare_o2c_graph_db(db_path)

    schema_summary_path = tmp_path / "schema_summary_o2c.json"
    write_schema_summary_json(schema_summary_path, db_path=db_path, schema_name="o2c")

    out = run_graph_full(
        run_id="rf11-o2c-graph-it",
        dataset_hash="rf11-o2c-hash",
        input_zip="rf11-o2c-input",
        run_metadata_overrides={
            "schema_summary_path": str(schema_summary_path),
            "catalog_path": "tests/catalog_o2c",
            "db_path": str(db_path),
            "schema_name": "o2c",
            "table_name": "o2c_order",
            "process_family": "o2c",
            "llm_mode": "stub",
            "kb_index_enabled": False,
            "kb_search_enabled": False,
            "persist_base_dir": str(tmp_path / "run_results"),
            "hypothesis_max_items": 4,
            "test_planner_top_n": 2,
        },
    )

    meta = out.run_metadata if isinstance(out.run_metadata, dict) else {}
    assert meta.get("graph_status") == "OK"
    assert meta.get("process_family") == "o2c"

    selected_tests = out.selected_tests if isinstance(out.selected_tests, list) else []
    assert selected_tests
    assert all(str(row.get("test_id", "")).startswith("TST-O2C-") for row in selected_tests if isinstance(row, dict))

    findings = out.findings if isinstance(out.findings, list) else []
    assert findings
    assert all(str(row.get("test_id", "")).startswith("TST-O2C-") for row in findings if isinstance(row, dict))

    if isinstance(meta.get("persist_artifacts"), dict):
        graph_state_path = meta["persist_artifacts"].get("graph_state_json", "")
        if graph_state_path:
            payload = json.loads(Path(graph_state_path).read_text(encoding="utf-8"))
            assert payload.get("run_metadata", {}).get("process_family") == "o2c"
