from __future__ import annotations

import duckdb

from src.erp_fraud.catalog import TestRunner


def _prepare_o2c_tables(conn: duckdb.DuckDBPyConnection) -> None:
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
        [
            ("8000000001", "000010", "5000000001", "000010", 15.0),
            ("8000000002", "000020", "5000000002", "000010", -3.0),
        ],
    )
    conn.executemany(
        'INSERT INTO "o2c"."o2c_collection" VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [
            ("1000", "1900000010", "2026", "V01", 20000.0, "2026-01-20", "2026-01-10", None),
        ],
    )


def test_rf11_o2c_catalog_tests_execute_with_runner(tmp_path) -> None:
    db_path = tmp_path / "o2c_tests.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _prepare_o2c_tables(conn)
    finally:
        conn.close()

    runner = TestRunner(db_path=db_path, schema_name="o2c", table_name="o2c_order")
    results = runner.run_all(
        selected_tests=[
            "TST-O2C-PRICE-OUTLIER",
            "TST-O2C-DISCOUNT-POLICY-BREACH",
            "TST-O2C-DELIVERY-QUANTITY-MISMATCH",
            "TST-O2C-NEGATIVE-DELIVERY-QUANTITY",
            "TST-O2C-CLEARING-ANOMALY",
        ],
        catalog_path="tests/catalog_o2c",
        validate_schema=True,
    )

    status_by_id = {str(r.get("test_id", "")): str(r.get("status", "")) for r in results if isinstance(r, dict)}
    assert status_by_id["TST-O2C-PRICE-OUTLIER"] == "OK"
    assert status_by_id["TST-O2C-DISCOUNT-POLICY-BREACH"] == "OK"
    assert status_by_id["TST-O2C-DELIVERY-QUANTITY-MISMATCH"] == "OK"
    assert status_by_id["TST-O2C-NEGATIVE-DELIVERY-QUANTITY"] == "OK"
    assert status_by_id["TST-O2C-CLEARING-ANOMALY"] == "OK"

    findings_by_id = {str(r.get("test_id", "")): int(r.get("finding_count", 0) or 0) for r in results if isinstance(r, dict)}
    assert findings_by_id["TST-O2C-PRICE-OUTLIER"] >= 1
    assert findings_by_id["TST-O2C-DISCOUNT-POLICY-BREACH"] >= 1
    assert findings_by_id["TST-O2C-DELIVERY-QUANTITY-MISMATCH"] >= 1
    assert findings_by_id["TST-O2C-NEGATIVE-DELIVERY-QUANTITY"] >= 1
    assert findings_by_id["TST-O2C-CLEARING-ANOMALY"] >= 1
