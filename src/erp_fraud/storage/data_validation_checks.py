"""Checks técnicos sobre DuckDB para validación de dataset (RF02b)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .data_validation_policy import get_validation_severity

if TYPE_CHECKING:
    import duckdb


DATE_KEYWORDS = ("date", "fecha", "datum", "timestamp", "uhrzeit", "zeit")
AMOUNT_KEYWORDS = ("betrag", "amount", "importe", "price", "precio", "cost", "wert", "skonto")


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _looks_like_date_column(column_name: str) -> bool:
    name = column_name.strip().lower()
    return any(k in name for k in DATE_KEYWORDS)


def _looks_like_amount_column(column_name: str) -> bool:
    name = column_name.strip().lower()
    if "wertestring" in name or "bewert" in name:
        return False
    return any(k in name for k in AMOUNT_KEYWORDS)


def _build_available_columns_index(conn: "duckdb.DuckDBPyConnection", schema_name: str) -> dict[str, set[str]]:
    rows = conn.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = ?
        """,
        [schema_name],
    ).fetchall()
    index: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        index.setdefault(str(table_name), set()).add(str(column_name))
    return index


def check_missing_required_columns_in_duckdb(
    required_columns_by_table: dict[str, list[str]],
    *,
    conn: "duckdb.DuckDBPyConnection | None" = None,
    db_path: str | Path = "erp.duckdb",
    schema_name: str = "main",
) -> dict:
    """Valida columnas requeridas en DuckDB y devuelve faltantes por tabla."""
    if conn is None:
        from .duckdb_store import get_duckdb_connection

    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    try:
        available_by_table = _build_available_columns_index(conn, schema_name)
    finally:
        if own_connection:
            conn.close()

    missing_by_table: dict[str, list[str]] = {}
    for table, required_columns in sorted(required_columns_by_table.items()):
        available = available_by_table.get(table, set())
        missing = sorted([c for c in required_columns if c not in available])
        if missing:
            missing_by_table[table] = missing

    check_name = "missing_required_columns"
    status = "OK" if not missing_by_table else "ERROR"
    return {
        "check_name": check_name,
        "severity": get_validation_severity(check_name),
        "status": status,
        "schema_name": schema_name,
        "tables_checked": len(required_columns_by_table),
        "missing_by_table": missing_by_table,
    }


def _count_unparseable_date_values(
    conn: "duckdb.DuckDBPyConnection", table: str, column: str
) -> int:
    query = f"""
        SELECT COUNT(*) AS cnt
        FROM {_quote_identifier(table)}
        WHERE { _quote_identifier(column) } IS NOT NULL
          AND TRIM(CAST({ _quote_identifier(column) } AS VARCHAR)) <> ''
          AND TRY_CAST({ _quote_identifier(column) } AS TIMESTAMP) IS NULL
          AND TRY_CAST({ _quote_identifier(column) } AS DATE) IS NULL
          AND TRY_CAST({ _quote_identifier(column) } AS TIME) IS NULL
    """
    return int(conn.execute(query).fetchone()[0])


def _count_unparseable_amount_values(
    conn: "duckdb.DuckDBPyConnection", table: str, column: str
) -> int:
    query = f"""
        SELECT COUNT(*) AS cnt
        FROM {_quote_identifier(table)}
        WHERE { _quote_identifier(column) } IS NOT NULL
          AND TRIM(CAST({ _quote_identifier(column) } AS VARCHAR)) <> ''
          AND TRY_CAST(REPLACE(TRIM(CAST({ _quote_identifier(column) } AS VARCHAR)), ',', '.') AS DOUBLE) IS NULL
    """
    return int(conn.execute(query).fetchone()[0])


def check_type_parse_errors_in_duckdb(
    required_columns_by_table: dict[str, list[str]],
    *,
    conn: "duckdb.DuckDBPyConnection | None" = None,
    db_path: str | Path = "erp.duckdb",
    schema_name: str = "main",
) -> dict:
    """Check de parseo para fechas e importes en columnas requeridas."""
    if conn is None:
        from .duckdb_store import get_duckdb_connection

    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    try:
        available_by_table = _build_available_columns_index(conn, schema_name)

        date_errors_by_col: dict[str, int] = {}
        amount_errors_by_col: dict[str, int] = {}
        skipped_missing_columns: list[str] = []
        date_columns_checked = 0
        amount_columns_checked = 0

        for table, columns in sorted(required_columns_by_table.items()):
            available = available_by_table.get(table, set())
            for column in columns:
                key = f"{table}.{column}"
                if column not in available:
                    skipped_missing_columns.append(key)
                    continue

                if _looks_like_date_column(column):
                    date_columns_checked += 1
                    count = _count_unparseable_date_values(conn, table, column)
                    if count > 0:
                        date_errors_by_col[key] = count

                if _looks_like_amount_column(column):
                    amount_columns_checked += 1
                    count = _count_unparseable_amount_values(conn, table, column)
                    if count > 0:
                        amount_errors_by_col[key] = count
    finally:
        if own_connection:
            conn.close()

    date_check_name = "type_parse_errors_dates"
    amount_check_name = "type_parse_errors_amounts"

    date_total_errors = sum(date_errors_by_col.values())
    amount_total_errors = sum(amount_errors_by_col.values())

    return {
        "date_check": {
            "check_name": date_check_name,
            "severity": get_validation_severity(date_check_name),
            "status": "OK" if date_total_errors == 0 else "ERROR",
            "columns_checked": date_columns_checked,
            "total_parse_errors": date_total_errors,
            "errors_by_column": date_errors_by_col,
        },
        "amount_check": {
            "check_name": amount_check_name,
            "severity": get_validation_severity(amount_check_name),
            "status": "OK" if amount_total_errors == 0 else "ERROR",
            "columns_checked": amount_columns_checked,
            "total_parse_errors": amount_total_errors,
            "errors_by_column": amount_errors_by_col,
        },
        "skipped_missing_columns": sorted(skipped_missing_columns),
        "schema_name": schema_name,
    }


def check_null_percentage_required_columns_in_duckdb(
    required_columns_by_table: dict[str, list[str]],
    *,
    conn: "duckdb.DuckDBPyConnection | None" = None,
    db_path: str | Path = "erp.duckdb",
    schema_name: str = "main",
) -> dict:
    """Calcula % de nulos por columna requerida disponible en DuckDB."""
    if conn is None:
        from .duckdb_store import get_duckdb_connection

    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    try:
        available_by_table = _build_available_columns_index(conn, schema_name)

        null_percent_by_column: dict[str, dict[str, float | int]] = {}
        skipped_missing_columns: list[str] = []

        for table, columns in sorted(required_columns_by_table.items()):
            available = available_by_table.get(table, set())
            for column in columns:
                key = f"{table}.{column}"
                if column not in available:
                    skipped_missing_columns.append(key)
                    continue

                query = f"""
                    SELECT
                        COUNT(*) AS total_rows,
                        SUM(
                            CASE
                                WHEN {_quote_identifier(column)} IS NULL THEN 1
                                WHEN TRIM(CAST({_quote_identifier(column)} AS VARCHAR)) = '' THEN 1
                                ELSE 0
                            END
                        ) AS null_rows
                    FROM {_quote_identifier(table)}
                """
                total_rows, null_rows = conn.execute(query).fetchone()
                total_rows = int(total_rows or 0)
                null_rows = int(null_rows or 0)
                null_pct = float((null_rows / total_rows) * 100.0) if total_rows > 0 else 0.0
                null_percent_by_column[key] = {
                    "total_rows": total_rows,
                    "null_rows": null_rows,
                    "null_percentage": round(null_pct, 4),
                }
    finally:
        if own_connection:
            conn.close()

    check_name = "null_percentage_required_columns"
    return {
        "check_name": check_name,
        "severity": get_validation_severity(check_name),
        "status": "OK",  # Warning por umbrales se decide en capa de reporte/política
        "columns_checked": len(null_percent_by_column),
        "null_percent_by_column": null_percent_by_column,
        "skipped_missing_columns": sorted(skipped_missing_columns),
        "schema_name": schema_name,
    }


def check_basic_ranges_in_duckdb(
    required_columns_by_table: dict[str, list[str]],
    *,
    conn: "duckdb.DuckDBPyConnection | None" = None,
    db_path: str | Path = "erp.duckdb",
    schema_name: str = "main",
) -> dict:
    """Reporte de rangos básicos para columnas requeridas de fecha e importe."""
    if conn is None:
        from .duckdb_store import get_duckdb_connection

    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    try:
        available_by_table = _build_available_columns_index(conn, schema_name)

        date_ranges_by_column: dict[str, dict[str, str | None | int]] = {}
        amount_ranges_by_column: dict[str, dict[str, float | int | None]] = {}
        skipped_missing_columns: list[str] = []
        date_columns_checked = 0
        amount_columns_checked = 0

        for table, columns in sorted(required_columns_by_table.items()):
            available = available_by_table.get(table, set())
            for column in columns:
                key = f"{table}.{column}"
                if column not in available:
                    skipped_missing_columns.append(key)
                    continue

                if _looks_like_date_column(column):
                    date_columns_checked += 1
                    query = f"""
                        WITH parsed AS (
                            SELECT COALESCE(
                                TRY_CAST({_quote_identifier(column)} AS TIMESTAMP),
                                TRY_CAST({_quote_identifier(column)} AS DATE)::TIMESTAMP
                            ) AS parsed_dt,
                            TRY_CAST({_quote_identifier(column)} AS TIME) AS parsed_tm
                            FROM {_quote_identifier(table)}
                            WHERE {_quote_identifier(column)} IS NOT NULL
                              AND TRIM(CAST({_quote_identifier(column)} AS VARCHAR)) <> ''
                        )
                        SELECT
                            MIN(parsed_dt) AS min_dt,
                            MAX(parsed_dt) AS max_dt,
                            MIN(parsed_tm) AS min_tm,
                            MAX(parsed_tm) AS max_tm,
                            SUM(CASE WHEN parsed_dt IS NULL AND parsed_tm IS NULL THEN 1 ELSE 0 END) AS parse_errors
                        FROM parsed
                    """
                    min_dt, max_dt, min_tm, max_tm, parse_errors = conn.execute(query).fetchone()
                    min_value = min_dt if min_dt is not None else min_tm
                    max_value = max_dt if max_dt is not None else max_tm
                    date_ranges_by_column[key] = {
                        "min": str(min_value) if min_value is not None else None,
                        "max": str(max_value) if max_value is not None else None,
                        "parse_errors": int(parse_errors or 0),
                    }

                if _looks_like_amount_column(column):
                    amount_columns_checked += 1
                    query = f"""
                        WITH parsed AS (
                            SELECT
                                TRY_CAST(
                                    REPLACE(TRIM(CAST({_quote_identifier(column)} AS VARCHAR)), ',', '.')
                                    AS DOUBLE
                                ) AS parsed_amount
                            FROM {_quote_identifier(table)}
                            WHERE {_quote_identifier(column)} IS NOT NULL
                              AND TRIM(CAST({_quote_identifier(column)} AS VARCHAR)) <> ''
                        )
                        SELECT
                            MIN(parsed_amount) AS min_amount,
                            MAX(parsed_amount) AS max_amount,
                            SUM(CASE WHEN parsed_amount < 0 THEN 1 ELSE 0 END) AS negative_count,
                            SUM(CASE WHEN parsed_amount IS NULL THEN 1 ELSE 0 END) AS parse_errors
                        FROM parsed
                    """
                    min_amount, max_amount, negative_count, parse_errors = conn.execute(query).fetchone()
                    amount_ranges_by_column[key] = {
                        "min": float(min_amount) if min_amount is not None else None,
                        "max": float(max_amount) if max_amount is not None else None,
                        "negative_count": int(negative_count or 0),
                        "parse_errors": int(parse_errors or 0),
                    }
    finally:
        if own_connection:
            conn.close()

    date_check_name = "basic_ranges_dates"
    amount_check_name = "basic_ranges_amounts"
    return {
        "date_ranges_check": {
            "check_name": date_check_name,
            "severity": get_validation_severity(date_check_name),
            "status": "OK",
            "columns_checked": date_columns_checked,
            "ranges_by_column": date_ranges_by_column,
        },
        "amount_ranges_check": {
            "check_name": amount_check_name,
            "severity": get_validation_severity(amount_check_name),
            "status": "OK",
            "columns_checked": amount_columns_checked,
            "ranges_by_column": amount_ranges_by_column,
        },
        "skipped_missing_columns": sorted(skipped_missing_columns),
        "schema_name": schema_name,
    }
