from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.erp_fraud.storage import (
    check_basic_ranges_in_duckdb,
    check_missing_required_columns_in_duckdb,
    check_null_percentage_required_columns_in_duckdb,
    check_type_parse_errors_in_duckdb,
    extract_required_columns_from_testspecs,
    get_duckdb_connection,
    get_validation_severity,
    is_critical_check,
    load_table_to_duckdb,
    run_technical_validation_before_tests,
    write_data_validation_report_json,
    write_or_update_report_markdown_with_data_validation,
)


def test_validation_policy_critical_vs_warning() -> None:
    assert get_validation_severity("missing_required_columns") == "critical"
    assert get_validation_severity("type_parse_errors_dates") == "critical"
    assert get_validation_severity("type_parse_errors_amounts") == "critical"
    assert get_validation_severity("null_percentage_required_columns") == "warning"
    assert is_critical_check("missing_required_columns") is True
    assert is_critical_check("basic_ranges_dates") is False


def test_extract_required_columns_from_testspecs() -> None:
    specs = [
        {
            "id": "T1",
            "data_requirements": {
                "fields": [{"table": "fraud_1", "column": "Belegnummer"}],
                "table_columns": {"fraud_1": ["Betrag"], "normal_1": ["Label"]},
            },
        }
    ]
    out = extract_required_columns_from_testspecs(specs)
    assert out == {"fraud_1": ["Belegnummer", "Betrag"], "normal_1": ["Label"]}


def _prepare_validation_db(tmp_path: Path) -> Path:
    db = tmp_path / "rf02b.duckdb"
    conn = get_duckdb_connection(db)
    try:
        load_table_to_duckdb(
            "fraud_1",
            pd.DataFrame(
                {
                    "Belegnummer": ["1", "", None, "4"],
                    "Betrag": ["10,0", "-2", "xx", ""],
                    "fecha_transaccion": ["2026-01-01", "bad-date", "", "2026-01-02"],
                    "Erfassungsuhrzeit": ["09:30:00", "bad-time", "", "10:15:10"],
                }
            ),
            conn=conn,
        )
    finally:
        conn.close()
    return db


def test_data_validation_checks_output(tmp_path: Path) -> None:
    db = _prepare_validation_db(tmp_path)
    required = {"fraud_1": ["Belegnummer", "Betrag", "fecha_transaccion", "Erfassungsuhrzeit"], "fraud_2": ["Betrag"]}

    conn = get_duckdb_connection(db)
    try:
        missing = check_missing_required_columns_in_duckdb(required, conn=conn)
        parse = check_type_parse_errors_in_duckdb(required, conn=conn)
        nulls = check_null_percentage_required_columns_in_duckdb(required, conn=conn)
        ranges = check_basic_ranges_in_duckdb(required, conn=conn)
    finally:
        conn.close()

    assert missing["status"] == "ERROR"
    assert "fraud_2" in missing["missing_by_table"]

    assert parse["date_check"]["check_name"] == "type_parse_errors_dates"
    assert parse["amount_check"]["check_name"] == "type_parse_errors_amounts"
    assert parse["date_check"]["total_parse_errors"] >= 1
    assert parse["amount_check"]["total_parse_errors"] >= 1

    assert nulls["check_name"] == "null_percentage_required_columns"
    assert "fraud_1.Belegnummer" in nulls["null_percent_by_column"]
    assert nulls["null_percent_by_column"]["fraud_1.Belegnummer"]["null_percentage"] > 0

    assert ranges["date_ranges_check"]["check_name"] == "basic_ranges_dates"
    assert ranges["amount_ranges_check"]["check_name"] == "basic_ranges_amounts"
    assert ranges["amount_ranges_check"]["ranges_by_column"]["fraud_1.Betrag"]["negative_count"] >= 1


def test_validation_report_and_pipeline_blocking(tmp_path: Path) -> None:
    db = _prepare_validation_db(tmp_path)
    required = {"fraud_1": ["Belegnummer", "Betrag", "fecha_transaccion"], "fraud_2": ["Betrag"]}
    report_json = tmp_path / "data_validation_report.json"
    report_md = tmp_path / "report.md"

    write_data_validation_report_json(
        report_json,
        required_columns_by_table=required,
        db_path=db,
    )
    assert report_json.exists()

    write_or_update_report_markdown_with_data_validation(
        report_md_path=report_md,
        data_validation_report_path=report_json,
    )
    assert report_md.exists()
    content = report_md.read_text(encoding="utf-8")
    assert "## Data Validation" in content
    assert "data_validation_report" in content

    # Caso crítico: incluye columna faltante en tabla inexistente -> bloquea
    specs_critical = [
        {
            "id": "T_CRIT",
            "data_requirements": {
                "fields": [
                    {"table": "fraud_1", "column": "Belegnummer"},
                    {"table": "fraud_2", "column": "Betrag"},
                ]
            },
        }
    ]
    out_critical = run_technical_validation_before_tests(
        test_specs=specs_critical,
        report_output_path=tmp_path / "pipeline_critical.json",
        db_path=db,
    )
    assert out_critical.should_block_run is True
    assert out_critical.critical_errors_count > 0

    # Caso warning-only: campos existentes y parseables en críticos -> no bloquea
    clean_db = tmp_path / "rf02b_clean.duckdb"
    conn = get_duckdb_connection(clean_db)
    try:
        load_table_to_duckdb(
            "fraud_1",
            pd.DataFrame(
                {
                    "Belegnummer": ["1", "", "3"],  # warning por nulos/string vacío
                    "Betrag": ["10,0", "-1", "20,0"],  # warning por negativo
                    "fecha_transaccion": ["2026-01-01", "2026-01-02", "2026-01-03"],  # parse OK
                }
            ),
            conn=conn,
        )
    finally:
        conn.close()

    specs_warning = [
        {
            "id": "T_WARN",
            "data_requirements": {
                "fields": [
                    {"table": "fraud_1", "column": "Belegnummer"},
                    {"table": "fraud_1", "column": "Betrag"},
                    {"table": "fraud_1", "column": "fecha_transaccion"},
                ]
            },
        }
    ]
    out_warning = run_technical_validation_before_tests(
        test_specs=specs_warning,
        report_output_path=tmp_path / "pipeline_warning.json",
        db_path=clean_db,
    )
    assert out_warning.should_block_run is False
    assert out_warning.critical_errors_count == 0
