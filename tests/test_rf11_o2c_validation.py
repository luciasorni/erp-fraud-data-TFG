from __future__ import annotations

import duckdb

from src.erp_fraud.storage.o2c_transform import transform_raw_to_o2c_canonical
from src.erp_fraud.storage.o2c_validation import build_o2c_validation_report


def _build_conn_with_minimal_o2c_sources(*, include_accounting: bool) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE main."VBAK" (
          "VBELN" VARCHAR,
          "KUNNR" VARCHAR,
          "ERDAT" VARCHAR,
          "VKORG" VARCHAR,
          "VTWEG" VARCHAR,
          "SPART" VARCHAR,
          "KNUMV" VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE main."VBAP" (
          "VBELN" VARCHAR,
          "POSNR" VARCHAR,
          "NETWR" DOUBLE,
          "MATNR" VARCHAR,
          "KWMENG" DOUBLE,
          "NETPR" DOUBLE
        )
        """
    )
    conn.execute("""CREATE TABLE main."VBPA" ("VBELN" VARCHAR, "KUNNR" VARCHAR)""")
    conn.execute(
        """CREATE TABLE main."KNA1" ("KUNNR" VARCHAR, "NAME1" VARCHAR, "LAND1" VARCHAR, "ORT01" VARCHAR, "KTOKD" VARCHAR, "KDGRP" VARCHAR)"""
    )
    conn.execute("""CREATE TABLE main."KONV" ("KNUMV" VARCHAR, "KWERT" DOUBLE)""")
    conn.execute(
        """CREATE TABLE main."LIPS" ("VBELN" VARCHAR, "POSNR" VARCHAR, "VGBEL" VARCHAR, "VGPOS" VARCHAR, "LFIMG" DOUBLE, "MATNR" VARCHAR, "WERKS" VARCHAR)"""
    )
    conn.execute("""CREATE TABLE main."LIKP" ("VBELN" VARCHAR, "LFDAT" VARCHAR, "WADAT_IST" VARCHAR, "KUNNR" VARCHAR)""")
    conn.execute("""CREATE TABLE main."KNB1" ("KUNNR" VARCHAR, "AKONT" VARCHAR, "ZTERM" VARCHAR, "MAHNA" VARCHAR)""")

    conn.execute("""INSERT INTO main."VBAK" VALUES ('5000000001', 'V01', '2026-01-01', '1000', '10', '00', 'C001')""")
    conn.execute("""INSERT INTO main."VBAP" VALUES ('5000000001', '000010', 1200.0, 'MAT-01', 10.0, 120.0)""")
    conn.execute("""INSERT INTO main."VBPA" VALUES ('5000000001', 'V01')""")
    conn.execute("""INSERT INTO main."KNA1" VALUES ('V01', 'Cliente Uno', 'ES', 'MADRID', 'Z001', 'GRP1')""")
    conn.execute("""INSERT INTO main."KONV" VALUES ('C001', -25.0)""")
    conn.execute("""INSERT INTO main."LIPS" VALUES ('8000000001', '000010', '5000000001', '000010', 10.0, 'MAT-01', 'P001')""")
    conn.execute("""INSERT INTO main."LIKP" VALUES ('8000000001', '2026-01-03', '2026-01-02', 'V01')""")
    conn.execute("""INSERT INTO main."KNB1" VALUES ('V01', '140000', '0001', 'A1')""")

    if include_accounting:
        conn.execute("""CREATE TABLE main."BKPF" ("BUKRS" VARCHAR, "BELNR" VARCHAR, "GJAHR" VARCHAR, "BUDAT" VARCHAR)""")
        conn.execute(
            """CREATE TABLE main."BSEG" ("BUKRS" VARCHAR, "BELNR" VARCHAR, "GJAHR" VARCHAR, "KUNNR" VARCHAR, "HKONT" VARCHAR, "DMBTR" DOUBLE, "WRBTR" DOUBLE, "SHKZG" VARCHAR, "ZFBDT" VARCHAR, "AUGBL" VARCHAR, "AUGDT" VARCHAR, "ZTERM" VARCHAR)"""
        )
        conn.execute("""INSERT INTO main."BKPF" VALUES ('1000', '1900000010', '2026', '2026-01-04')""")
        conn.execute(
            """INSERT INTO main."BSEG" VALUES ('1000', '1900000010', '2026', 'V01', '400000', 1200.0, 1200.0, 'H', '2026-01-15', '2000000001', '2026-01-20', '0001')"""
        )

    return conn


def test_rf11_06_validation_ok_with_full_o2c_entities() -> None:
    conn = _build_conn_with_minimal_o2c_sources(include_accounting=True)
    transform_raw_to_o2c_canonical(conn=conn)

    report = build_o2c_validation_report(conn=conn)
    summary = report.get("summary", {})
    assert summary.get("overall_status") == "OK"
    assert int(summary.get("critical_errors_count", 0)) == 0


def test_rf11_06_validation_ok_with_soft_fail_entities_missing() -> None:
    conn = _build_conn_with_minimal_o2c_sources(include_accounting=False)
    transform_raw_to_o2c_canonical(conn=conn)

    report = build_o2c_validation_report(conn=conn)
    summary = report.get("summary", {})
    assert summary.get("overall_status") == "OK"
    checks = report.get("checks", [])
    skipped_ids = {c.get("id") for c in checks if isinstance(c, dict) and c.get("status") == "SKIPPED"}
    assert "o2c_invoice.table_exists" in skipped_ids
    assert "o2c_collection.table_exists" in skipped_ids


def test_rf11_06_validation_error_when_fail_fast_table_missing() -> None:
    conn = duckdb.connect(":memory:")
    conn.execute('CREATE SCHEMA IF NOT EXISTS "o2c"')
    conn.execute('CREATE TABLE o2c."o2c_customer" (customer_id VARCHAR, customer_name VARCHAR)')
    conn.execute("INSERT INTO o2c.\"o2c_customer\" VALUES ('V01', 'Cliente Uno')")

    report = build_o2c_validation_report(conn=conn)
    summary = report.get("summary", {})
    assert summary.get("overall_status") == "ERROR"
    assert int(summary.get("critical_errors_count", 0)) >= 1

