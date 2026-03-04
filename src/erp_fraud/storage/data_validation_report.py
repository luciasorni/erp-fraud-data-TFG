"""Generación de data_validation_report.json (RF02b-07)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .data_validation_checks import (
    check_basic_ranges_in_duckdb,
    check_missing_required_columns_in_duckdb,
    check_null_percentage_required_columns_in_duckdb,
    check_type_parse_errors_in_duckdb,
)
from .data_validation_policy import is_critical_check
from .duckdb_store import DEFAULT_DUCKDB_PATH, get_duckdb_connection

if TYPE_CHECKING:
    import duckdb


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _count_missing_columns(missing_by_table: dict[str, list[str]]) -> int:
    return sum(len(cols) for cols in missing_by_table.values())


def build_data_validation_report(
    required_columns_by_table: dict[str, list[str]],
    *,
    conn: "duckdb.DuckDBPyConnection | None" = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    schema_name: str = "main",
    generated_at_utc: str | None = None,
) -> dict:
    """Ejecuta checks técnicos y devuelve reporte consolidado/estable."""
    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    try:
        missing = check_missing_required_columns_in_duckdb(
            required_columns_by_table,
            conn=conn,
            schema_name=schema_name,
        )
        parse = check_type_parse_errors_in_duckdb(
            required_columns_by_table,
            conn=conn,
            schema_name=schema_name,
        )
        nulls = check_null_percentage_required_columns_in_duckdb(
            required_columns_by_table,
            conn=conn,
            schema_name=schema_name,
        )
        ranges = check_basic_ranges_in_duckdb(
            required_columns_by_table,
            conn=conn,
            schema_name=schema_name,
        )
    finally:
        if own_connection:
            conn.close()

    # Normalización a estructura plana por check_name
    checks = {
        missing["check_name"]: missing,
        parse["date_check"]["check_name"]: parse["date_check"],
        parse["amount_check"]["check_name"]: parse["amount_check"],
        nulls["check_name"]: nulls,
        ranges["date_ranges_check"]["check_name"]: ranges["date_ranges_check"],
        ranges["amount_ranges_check"]["check_name"]: ranges["amount_ranges_check"],
    }

    # Métricas agregadas de severidad
    critical_errors_count = (
        _count_missing_columns(missing.get("missing_by_table", {}))
        + int(parse["date_check"].get("total_parse_errors", 0))
        + int(parse["amount_check"].get("total_parse_errors", 0))
    )

    warning_findings_count = 0
    warning_findings_count += sum(
        1
        for item in nulls.get("null_percent_by_column", {}).values()
        if float(item.get("null_percentage", 0.0)) > 0.0
    )
    warning_findings_count += sum(
        1
        for item in ranges["date_ranges_check"].get("ranges_by_column", {}).values()
        if int(item.get("parse_errors", 0)) > 0
    )
    warning_findings_count += sum(
        1
        for item in ranges["amount_ranges_check"].get("ranges_by_column", {}).values()
        if int(item.get("parse_errors", 0)) > 0 or int(item.get("negative_count", 0)) > 0
    )

    overall_status = "OK"
    for check_name, check in checks.items():
        if is_critical_check(check_name) and check.get("status") == "ERROR":
            overall_status = "ERROR"
            break

    return {
        "report_version": "1.0.0",
        "generated_at_utc": generated_at_utc or _utc_timestamp_iso(),
        "schema_name": schema_name,
        "required_columns_by_table": {
            table: sorted(columns) for table, columns in sorted(required_columns_by_table.items())
        },
        "summary": {
            "overall_status": overall_status,
            "critical_errors_count": critical_errors_count,
            "warning_findings_count": warning_findings_count,
            "checks_total": len(checks),
        },
        "checks": {name: checks[name] for name in sorted(checks.keys())},
        "meta": {
            "missing_columns_skipped_in_other_checks": sorted(
                set(parse.get("skipped_missing_columns", []))
                | set(nulls.get("skipped_missing_columns", []))
                | set(ranges.get("skipped_missing_columns", []))
            ),
        },
    }


def write_data_validation_report_json(
    output_path: str | Path,
    *,
    required_columns_by_table: dict[str, list[str]],
    conn: "duckdb.DuckDBPyConnection | None" = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    schema_name: str = "main",
) -> Path:
    """Genera `data_validation_report.json` con estructura estable."""
    report = build_data_validation_report(
        required_columns_by_table,
        conn=conn,
        db_path=db_path,
        schema_name=schema_name,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
