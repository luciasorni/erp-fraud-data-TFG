from __future__ import annotations

import duckdb
import pandas as pd

from src.erp_fraud.catalog import (
    load_test_specs_from_catalog,
    run_test_duplicate_postings,
    run_test_round_dollar_payments,
    run_test_unusual_amount_by_vendor,
    validate_result_schema,
)


def _spec_by_id(catalog_specs: list[dict], test_id: str) -> dict:
    for spec in catalog_specs:
        if spec.get("id") == test_id:
            return spec
    raise AssertionError(f"No se encontró TestSpec: {test_id}")


def _build_test_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE fraud_1 (Kreditor VARCHAR, Belegnummer VARCHAR, Position VARCHAR, Betrag DOUBLE, Transaktionsart VARCHAR)"
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?)",
        [
            ("V1", "D1", "10", 100.0, "N"),
            ("V1", "D1", "10", 100.0, "N"),
            ("V1", "D2", "10", 101.0, "N"),
            ("V1", "D3", "10", 99.0, "N"),
            ("V1", "D4", "10", 100.0, "N"),
            ("V1", "D5", "10", 500.0, "N"),
            ("V2", "D6", "10", 10.0, "N"),
            ("V2", "D7", "10", 11.0, "N"),
            ("V3", "D8", "10", 250.0, "N"),
            ("V3", "D9", "10", 250.5, "N"),
        ],
    )
    return conn


def test_rf13_family_duplicate_payment_result_schema() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-DUPLICATE-POSTINGS")
    conn = _build_test_conn()
    try:
        out = run_test_duplicate_postings(spec, conn=conn, table_name="fraud_1", schema_name="main")
    finally:
        conn.close()

    assert out["fraud_type"] == "duplicate_payment"
    assert out["finding_count"] >= 1
    validate_result_schema(pd.DataFrame(out["rows"]))


def test_rf13_family_amount_anomaly_result_schema() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-UNUSUAL-AMOUNT-BY-VENDOR")
    conn = _build_test_conn()
    try:
        out = run_test_unusual_amount_by_vendor(
            spec,
            conn=conn,
            table_name="fraud_1",
            schema_name="main",
            min_rows_per_vendor=5,
            z_threshold=1.7,
        )
    finally:
        conn.close()

    assert out["fraud_type"] == "amount_anomaly"
    assert out["finding_count"] >= 1
    validate_result_schema(pd.DataFrame(out["rows"]))


def test_rf13_family_payment_pattern_result_schema() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-ROUND-DOLLAR-PAYMENTS")
    conn = _build_test_conn()
    try:
        out = run_test_round_dollar_payments(spec, conn=conn, table_name="fraud_1", schema_name="main")
    finally:
        conn.close()

    assert out["fraud_type"] == "suspicious_payment_pattern"
    assert out["finding_count"] >= 1
    validate_result_schema(pd.DataFrame(out["rows"]))
