"""Ejecución de tests del catálogo RF03 (implementaciones iniciales)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb

from ..storage.duckdb_store import DEFAULT_DUCKDB_PATH, get_duckdb_connection

STANDARD_TEST_RESULT_SCHEMA_VERSION = "1.0.0"


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _quote_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("identifier debe ser string no vacío")
    return '"' + identifier.strip().replace('"', '""') + '"'


def build_standard_test_result(
    *,
    test_spec: dict[str, Any],
    status: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    duration_ms: int,
    implementation_type: str,
    executed_on: str,
) -> dict[str, Any]:
    """Devuelve resultado estandarizado para tests de catálogo."""
    return {
        "result_schema_version": STANDARD_TEST_RESULT_SCHEMA_VERSION,
        "generated_at_utc": _utc_timestamp_iso(),
        "test_id": str(test_spec.get("id", "")),
        "test_version": str(test_spec.get("version", "")),
        "fraud_type": str(test_spec.get("fraud_type", "")),
        "status": status,
        "finding_count": len(rows),
        "duration_ms": int(duration_ms),
        "columns": columns,
        "rows": rows,
        "metadata": {
            "implementation_type": implementation_type,
            "executed_on": executed_on,
        },
    }


def run_test_duplicate_postings(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    max_rows: int = 1000,
) -> dict[str, Any]:
    """Ejecuta TST-DUPLICATE-POSTINGS y devuelve resultado estándar."""
    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    quoted_schema = _quote_identifier(schema_name)
    quoted_table = _quote_identifier(table_name)
    qualified_table = f"{quoted_schema}.{quoted_table}"
    executed_on = f"{schema_name}.{table_name}"

    query = f"""
        SELECT
            "Kreditor" AS kreditor,
            "Belegnummer" AS belegnummer,
            "Position" AS position,
            "Betrag" AS betrag,
            COUNT(*) AS duplicate_count
        FROM {qualified_table}
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, kreditor, belegnummer, position
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = ["kreditor", "belegnummer", "position", "betrag", "duplicate_count"]
    rows = [
        {
            "kreditor": row[0],
            "belegnummer": row[1],
            "position": row[2],
            "betrag": row[3],
            "duplicate_count": int(row[4]),
        }
        for row in raw_rows
    ]

    return build_standard_test_result(
        test_spec=test_spec,
        status="OK",
        rows=rows,
        columns=columns,
        duration_ms=duration_ms,
        implementation_type="sql",
        executed_on=executed_on,
    )


def run_test_unusual_amount_by_vendor(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    min_rows_per_vendor: int = 5,
    z_threshold: float = 3.0,
    max_rows: int = 1000,
) -> dict[str, Any]:
    """Ejecuta TST-UNUSUAL-AMOUNT-BY-VENDOR y devuelve resultado estándar."""
    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    quoted_schema = _quote_identifier(schema_name)
    quoted_table = _quote_identifier(table_name)
    qualified_table = f"{quoted_schema}.{quoted_table}"
    executed_on = f"{schema_name}.{table_name}"

    query = f"""
        WITH base AS (
            SELECT
                "Kreditor" AS kreditor,
                TRY_CAST("Betrag" AS DOUBLE) AS betrag,
                "Transaktionsart" AS transaktionsart
            FROM {qualified_table}
            WHERE "Kreditor" IS NOT NULL
              AND TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
        ),
        stats AS (
            SELECT
                kreditor,
                COUNT(*) AS n_rows,
                AVG(betrag) AS mean_betrag,
                STDDEV_SAMP(betrag) AS std_betrag
            FROM base
            GROUP BY 1
            HAVING COUNT(*) >= ?
        )
        SELECT
            b.kreditor,
            b.transaktionsart,
            b.betrag,
            s.n_rows,
            s.mean_betrag,
            s.std_betrag,
            ABS((b.betrag - s.mean_betrag) / NULLIF(s.std_betrag, 0)) AS z_score
        FROM base b
        JOIN stats s USING (kreditor)
        WHERE s.std_betrag IS NOT NULL
          AND s.std_betrag > 0
          AND ABS((b.betrag - s.mean_betrag) / s.std_betrag) >= ?
        ORDER BY z_score DESC, b.kreditor
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [min_rows_per_vendor, z_threshold, max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = [
        "kreditor",
        "transaktionsart",
        "betrag",
        "n_rows",
        "mean_betrag",
        "std_betrag",
        "z_score",
    ]
    rows = [
        {
            "kreditor": row[0],
            "transaktionsart": row[1],
            "betrag": row[2],
            "n_rows": int(row[3]),
            "mean_betrag": row[4],
            "std_betrag": row[5],
            "z_score": row[6],
        }
        for row in raw_rows
    ]

    return build_standard_test_result(
        test_spec=test_spec,
        status="OK",
        rows=rows,
        columns=columns,
        duration_ms=duration_ms,
        implementation_type="sql",
        executed_on=executed_on,
    )
