from __future__ import annotations

import json
from pathlib import Path
import zipfile

import duckdb

from src.erp_fraud.cli.main import main


def _write_dummy_zip(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("dummy.txt", "rf11-o2c")


def _prepare_o2c_min_sources(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
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
        conn.execute("""CREATE TABLE main."BKPF" ("BUKRS" VARCHAR, "BELNR" VARCHAR, "GJAHR" VARCHAR, "BUDAT" VARCHAR)""")
        conn.execute(
            """CREATE TABLE main."BSEG" ("BUKRS" VARCHAR, "BELNR" VARCHAR, "GJAHR" VARCHAR, "KUNNR" VARCHAR, "HKONT" VARCHAR, "DMBTR" DOUBLE, "WRBTR" DOUBLE, "SHKZG" VARCHAR, "ZFBDT" VARCHAR, "AUGBL" VARCHAR, "AUGDT" VARCHAR, "ZTERM" VARCHAR)"""
        )

        conn.execute("""INSERT INTO main."VBAK" VALUES ('5000000001', 'V01', '2026-01-01', '1000', '10', '00', 'C001')""")
        conn.execute("""INSERT INTO main."VBAP" VALUES ('5000000001', '000010', 1200.0, 'MAT-01', 10.0, 120.0)""")
        conn.execute("""INSERT INTO main."VBPA" VALUES ('5000000001', 'V01')""")
        conn.execute("""INSERT INTO main."KNA1" VALUES ('V01', 'Cliente Uno', 'ES', 'MADRID', 'Z001', 'GRP1')""")
        conn.execute("""INSERT INTO main."KONV" VALUES ('C001', -25.0)""")
        conn.execute("""INSERT INTO main."LIPS" VALUES ('8000000001', '000010', '5000000001', '000010', 10.0, 'MAT-01', 'P001')""")
        conn.execute("""INSERT INTO main."LIKP" VALUES ('8000000001', '2026-01-03', '2026-01-02', 'V01')""")
        conn.execute("""INSERT INTO main."KNB1" VALUES ('V01', '140000', '0001', 'A1')""")
        conn.execute("""INSERT INTO main."BKPF" VALUES ('1000', '1900000010', '2026', '2026-01-04')""")
        conn.execute(
            """INSERT INTO main."BSEG" VALUES ('1000', '1900000010', '2026', 'V01', '400000', 1200.0, 1200.0, 'H', '2026-01-15', '2000000001', '2026-01-20', '0001')"""
        )
    finally:
        conn.close()


def test_rf11_08_cli_run_o2c_mode_generates_artifacts(tmp_path: Path) -> None:
    db_path = tmp_path / "erp_o2c.duckdb"
    zip_path = tmp_path / "dummy.zip"
    _write_dummy_zip(zip_path)
    _prepare_o2c_min_sources(db_path)

    run_id = "rf11-08-o2c-ok"
    rc = main(
        [
            "run",
            "--input-zip",
            str(zip_path),
            "--db-path",
            str(db_path),
            "--out-dir",
            str(tmp_path / "run_results"),
            "--run-id",
            run_id,
            "--process-family",
            "o2c",
        ]
    )
    assert rc == 0

    run_dir = tmp_path / "run_results" / run_id
    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "schema_summary.json").exists()
    assert (run_dir / "data_validation_report.json").exists()
    assert (run_dir / "report.json").exists()
    assert (run_dir / "report.md").exists()

    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["process_family"] == "o2c"
    assert metadata.get("o2c_target_schema") == "o2c"
    assert isinstance(metadata.get("o2c_transform_status"), dict)

    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["overall_status"] == "OK"
    assert int(report["summary"]["tests_total"]) == 0
    assert int(report["summary"]["ranking_entities"]) == 0
    assert report.get("test_runs") == []
    ranking_obj = report.get("ranking", {})
    assert isinstance(ranking_obj, dict)
    assert ranking_obj.get("rows") == []
    extra = report["metadata"]["metadata_extra"]
    assert extra["process_family"] == "o2c"
    assert extra["o2c_target_schema"] == "o2c"


def test_rf11_08_cli_run_o2c_mode_fails_when_missing_fail_fast_sources(tmp_path: Path) -> None:
    db_path = tmp_path / "erp_o2c_fail.duckdb"
    zip_path = tmp_path / "dummy.zip"
    _write_dummy_zip(zip_path)

    # Solo VBAP, sin VBAK (fail-fast para o2c_order)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("""CREATE TABLE main."VBAP" ("VBELN" VARCHAR, "POSNR" VARCHAR, "NETWR" DOUBLE)""")
        conn.execute("""INSERT INTO main."VBAP" VALUES ('5000000001', '000010', 100.0)""")
    finally:
        conn.close()

    rc = main(
        [
            "run",
            "--input-zip",
            str(zip_path),
            "--db-path",
            str(db_path),
            "--out-dir",
            str(tmp_path / "run_results"),
            "--run-id",
            "rf11-08-o2c-fail",
            "--process-family",
            "o2c",
        ]
    )
    assert rc == 1
