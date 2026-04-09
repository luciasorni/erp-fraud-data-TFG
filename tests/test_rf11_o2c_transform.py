from __future__ import annotations

import duckdb
import pytest

from src.erp_fraud.storage.o2c_transform import O2CTransformError, transform_raw_to_o2c_canonical


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
    conn.execute(
        """
        CREATE TABLE main."VBPA" (
          "VBELN" VARCHAR,
          "KUNNR" VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE main."KNA1" (
          "KUNNR" VARCHAR,
          "NAME1" VARCHAR,
          "LAND1" VARCHAR,
          "ORT01" VARCHAR,
          "KTOKD" VARCHAR,
          "KDGRP" VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE main."KONV" (
          "KNUMV" VARCHAR,
          "KWERT" DOUBLE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE main."LIPS" (
          "VBELN" VARCHAR,
          "POSNR" VARCHAR,
          "VGBEL" VARCHAR,
          "VGPOS" VARCHAR,
          "LFIMG" DOUBLE,
          "MATNR" VARCHAR,
          "WERKS" VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE main."LIKP" (
          "VBELN" VARCHAR,
          "LFDAT" VARCHAR,
          "WADAT_IST" VARCHAR,
          "KUNNR" VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE main."KNB1" (
          "KUNNR" VARCHAR,
          "AKONT" VARCHAR,
          "ZTERM" VARCHAR,
          "MAHNA" VARCHAR
        )
        """
    )

    conn.execute("""INSERT INTO main."VBAK" VALUES ('5000000001', 'V01', '2026-01-01', '1000', '10', '00', 'C001')""")
    conn.execute("""INSERT INTO main."VBAP" VALUES ('5000000001', '000010', 1200.0, 'MAT-01', 10.0, 120.0)""")
    conn.execute("""INSERT INTO main."VBPA" VALUES ('5000000001', 'V01')""")
    conn.execute("""INSERT INTO main."KNA1" VALUES ('V01', 'Cliente Uno', 'ES', 'MADRID', 'Z001', 'GRP1')""")
    conn.execute("""INSERT INTO main."KONV" VALUES ('C001', -25.0)""")
    conn.execute("""INSERT INTO main."LIPS" VALUES ('8000000001', '000010', '5000000001', '000010', 10.0, 'MAT-01', 'P001')""")
    conn.execute("""INSERT INTO main."LIKP" VALUES ('8000000001', '2026-01-03', '2026-01-02', 'V01')""")
    conn.execute("""INSERT INTO main."KNB1" VALUES ('V01', '140000', '0001', 'A1')""")

    if include_accounting:
        conn.execute(
            """
            CREATE TABLE main."BKPF" (
              "BUKRS" VARCHAR,
              "BELNR" VARCHAR,
              "GJAHR" VARCHAR,
              "BUDAT" VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE main."BSEG" (
              "BUKRS" VARCHAR,
              "BELNR" VARCHAR,
              "GJAHR" VARCHAR,
              "KUNNR" VARCHAR,
              "HKONT" VARCHAR,
              "DMBTR" DOUBLE,
              "WRBTR" DOUBLE,
              "SHKZG" VARCHAR,
              "ZFBDT" VARCHAR,
              "AUGBL" VARCHAR,
              "AUGDT" VARCHAR,
              "ZTERM" VARCHAR
            )
            """
        )
        conn.execute("""INSERT INTO main."BKPF" VALUES ('1000', '1900000010', '2026', '2026-01-04')""")
        conn.execute(
            """INSERT INTO main."BSEG" VALUES ('1000', '1900000010', '2026', 'V01', '400000', 1200.0, 1200.0, 'H', '2026-01-15', '2000000001', '2026-01-20', '0001')"""
        )

    return conn


def test_rf11_05_transform_builds_o2c_schema_when_sources_present() -> None:
    conn = _build_conn_with_minimal_o2c_sources(include_accounting=True)

    out = transform_raw_to_o2c_canonical(conn=conn)
    assert out["entities_ok"] == 5
    assert out["entities_skipped"] == 0
    assert out["mapping_config_path"] == "config/column_mapping_o2c.yaml"

    for entity in ["o2c_order", "o2c_delivery", "o2c_invoice", "o2c_collection", "o2c_customer"]:
        row = conn.execute(f'SELECT COUNT(*) FROM o2c."{entity}"').fetchone()
        assert isinstance(row, tuple)
        assert int(row[0]) >= 1


def test_rf11_05_transform_skips_soft_fail_entities_when_accounting_missing() -> None:
    conn = _build_conn_with_minimal_o2c_sources(include_accounting=False)

    out = transform_raw_to_o2c_canonical(conn=conn)
    status = {row["entity"]: row for row in out["entity_status"]}
    assert status["o2c_order"]["status"] == "OK"
    assert status["o2c_delivery"]["status"] == "OK"
    assert status["o2c_customer"]["status"] == "OK"
    assert status["o2c_invoice"]["status"] == "SKIPPED"
    assert status["o2c_collection"]["status"] == "SKIPPED"

    assert conn.execute("""SELECT COUNT(*) FROM o2c."o2c_order" """).fetchone()[0] >= 1
    assert conn.execute("""SELECT COUNT(*) FROM o2c."o2c_delivery" """).fetchone()[0] >= 1
    assert conn.execute("""SELECT COUNT(*) FROM o2c."o2c_customer" """).fetchone()[0] >= 1


def test_rf11_05_transform_fails_when_fail_fast_entity_required_table_missing() -> None:
    conn = duckdb.connect(":memory:")
    conn.execute("""CREATE TABLE main."VBAP" ("VBELN" VARCHAR, "POSNR" VARCHAR, "NETWR" DOUBLE)""")
    conn.execute("""INSERT INTO main."VBAP" VALUES ('5000000001', '000010', 100.0)""")

    with pytest.raises(O2CTransformError):
        transform_raw_to_o2c_canonical(conn=conn)
