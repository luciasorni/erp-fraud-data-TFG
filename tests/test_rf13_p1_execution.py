from __future__ import annotations

import duckdb

from src.erp_fraud.catalog import (
    load_test_specs_from_catalog,
    run_test_duplicate_material_items,
    run_test_invoice_sequence_gaps,
    run_test_just_below_auth_threshold,
    run_test_negative_quantity_receipts,
    run_test_split_payments_near_limit,
)


def _spec_by_id(catalog_specs: list[dict], test_id: str) -> dict:
    for spec in catalog_specs:
        if spec.get("id") == test_id:
            return spec
    raise AssertionError(f"No se encontró TestSpec: {test_id}")


def _build_conn_p1() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE fraud_1 (
            Kreditor VARCHAR,
            Belegnummer VARCHAR,
            Position VARCHAR,
            Betrag DOUBLE,
            Transaktionsart VARCHAR,
            Menge DOUBLE,
            Material VARCHAR
        )
        """
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("V1", "1001", "10", 99.0, "N", 5.0, "M1"),   # just-below-100
            ("V1", "1002", "10", 490.0, "N", 2.0, "M2"),  # just-below-500
            ("V2", "2001", "10", 600.0, "N", -1.0, "M3"),  # negative qty
            ("V3", "3001", "10", 600.0, "N", 1.0, "M4"),   # split line 1
            ("V3", "3001", "20", 450.0, "N", 1.0, "M4"),   # split line 2 total 1050
            ("V4", "4001", "10", 100.0, "N", 1.0, "M5"),
            ("V4", "4015", "10", 120.0, "N", 1.0, "M6"),   # sequence gap 14
            ("V5", "5001", "10", 10.0, "N", 1.0, "MX"),
            ("V5", "5001", "10", 12.0, "N", 1.0, "MX"),    # duplicate material
        ],
    )
    return conn


def test_rf13_p1_just_below_auth_threshold_executes() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-JUST-BELOW-AUTH-THRESHOLD")
    conn = _build_conn_p1()
    try:
        out = run_test_just_below_auth_threshold(spec, conn=conn, table_name="fraud_1", schema_name="main")
    finally:
        conn.close()
    assert out["status"] == "OK"
    assert out["finding_count"] >= 1


def test_rf13_p1_split_payments_near_limit_executes() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-SPLIT-PAYMENTS-NEAR-LIMIT")
    conn = _build_conn_p1()
    try:
        out = run_test_split_payments_near_limit(spec, conn=conn, table_name="fraud_1", schema_name="main")
    finally:
        conn.close()
    assert out["status"] == "OK"
    assert out["finding_count"] >= 1


def test_rf13_p1_invoice_sequence_gaps_executes() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-INVOICE-SEQUENCE-GAPS")
    conn = _build_conn_p1()
    try:
        out = run_test_invoice_sequence_gaps(spec, conn=conn, table_name="fraud_1", schema_name="main")
    finally:
        conn.close()
    assert out["status"] == "OK"
    assert out["finding_count"] >= 1


def test_rf13_p1_negative_quantity_receipts_executes() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-NEGATIVE-QUANTITY-RECEIPTS")
    conn = _build_conn_p1()
    try:
        out = run_test_negative_quantity_receipts(spec, conn=conn, table_name="fraud_1", schema_name="main")
    finally:
        conn.close()
    assert out["status"] == "OK"
    assert out["finding_count"] >= 1


def test_rf13_p1_duplicate_material_items_executes() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-DUPLICATE-MATERIAL-ITEMS")
    conn = _build_conn_p1()
    try:
        out = run_test_duplicate_material_items(spec, conn=conn, table_name="fraud_1", schema_name="main")
    finally:
        conn.close()
    assert out["status"] == "OK"
    assert out["finding_count"] >= 1
