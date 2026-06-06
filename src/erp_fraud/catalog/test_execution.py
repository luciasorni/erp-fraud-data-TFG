"""Ejecución de tests del catálogo RF03 (implementaciones iniciales)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb

from ..storage.duckdb_store import DEFAULT_DUCKDB_PATH, get_duckdb_connection
from .drilldown_templates import build_drilldown_template_ref
from .entity_key import build_entity_key
from .drilldown_keys import get_minimum_keys_for_test_id
from .result_schema import RESULT_SCHEMA_VERSION

STANDARD_TEST_RESULT_SCHEMA_VERSION = RESULT_SCHEMA_VERSION
APP_ROOT = Path("/app")


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _quote_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("identifier debe ser string no vacío")
    return '"' + identifier.strip().replace('"', '""') + '"'


def _catalog_yaml_dir_from_test_spec(test_spec: dict[str, Any]) -> Path | None:
    candidates = (
        test_spec.get("_catalog_source_path"),
        test_spec.get("_source_path"),
        test_spec.get("catalog_source_path"),
        test_spec.get("source_path"),
    )
    for candidate in candidates:
        raw = str(candidate or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if path.is_file():
            return path.parent
        if path.suffix.lower() in {".yaml", ".yml"}:
            return path.parent
    return None


def _resolve_sql_ref_path(*, test_spec: dict[str, Any], sql_ref: str) -> Path:
    sql_path = Path(sql_ref)
    candidates: list[Path] = []
    if sql_path.is_absolute():
        candidates.append(sql_path)
    else:
        candidates.extend(
            [
                Path.cwd() / sql_path,
                APP_ROOT / sql_path,
            ]
        )
        catalog_dir = _catalog_yaml_dir_from_test_spec(test_spec)
        if catalog_dir is not None:
            candidates.append(catalog_dir / sql_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = candidates or [sql_path]
    raise FileNotFoundError(f"No existe SQL ref: {searched[0]}")


def _build_finding_common_fields(
    *,
    test_id: str,
    keys: dict[str, str],
    evidence_columns: list[str],
    metrics: dict[str, object],
) -> dict[str, object]:
    min_keys = get_minimum_keys_for_test_id(test_id)
    missing = [name for name in min_keys if name not in keys]
    if missing:
        raise ValueError(f"keys incompletas para {test_id}: faltan {missing}")
    return {
        "keys": keys,
        "entity_key": build_entity_key(keys),
        "evidence_columns": evidence_columns,
        "metrics": metrics,
        "drilldown_template": build_drilldown_template_ref(
            test_id=test_id,
            keys=keys,
        ),
    }


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


def _annotate_o2c_discount_applicability(
    *,
    test_spec: dict[str, Any],
    result: dict[str, Any],
    conn: duckdb.DuckDBPyConnection,
    schema_name: str,
) -> dict[str, Any]:
    test_id = str(test_spec.get("id", "")).strip()
    if test_id != "TST-O2C-DISCOUNT-POLICY-BREACH":
        return result
    if int(result.get("finding_count", 0) or 0) > 0:
        return result
    try:
        row = conn.execute(
            f'''
            SELECT
              COUNT(*) AS total_rows,
              SUM(CASE WHEN condition_amount IS NOT NULL THEN 1 ELSE 0 END) AS nonnull_condition_amount_rows
            FROM "{schema_name}"."o2c_order"
            '''
        ).fetchone()
    except Exception:
        return result
    total_rows = int(row[0] or 0) if row else 0
    nonnull_rows = int(row[1] or 0) if row else 0
    metadata = result.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        result["metadata"] = metadata
    if total_rows > 0 and nonnull_rows == 0:
        result["status"] = "SKIPPED"
        result["error_summary"] = "LOW_APPLICABILITY: condition_amount no disponible en o2c_order; revisar fuente KONV/datos de descuento."
        metadata["applicability_status"] = "LOW"
        metadata["applicability_reason"] = "condition_amount no disponible en o2c_order; el dataset no aporta señal real de descuentos."
    return result


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
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "belegnummer": str(base["belegnummer"]),
                        "position": str(base["position"]),
                        "betrag": str(base["betrag"]),
                    },
                    evidence_columns=["kreditor", "belegnummer", "position", "betrag", "duplicate_count"],
                    metrics={"duplicate_count": int(base["duplicate_count"])},
                ),
            }
        )(
            {
                "kreditor": row[0],
                "belegnummer": row[1],
                "position": row[2],
                "betrag": row[3],
                "duplicate_count": int(row[4]),
            }
        )
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
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "betrag": str(base["betrag"]),
                        "transaktionsart": str(base["transaktionsart"]),
                    },
                    evidence_columns=[
                        "kreditor",
                        "transaktionsart",
                        "betrag",
                        "n_rows",
                        "mean_betrag",
                        "std_betrag",
                        "z_score",
                    ],
                    metrics={"z_score": float(base["z_score"]) if base["z_score"] is not None else None},
                ),
            }
        )(
            {
                "kreditor": row[0],
                "transaktionsart": row[1],
                "betrag": row[2],
                "n_rows": int(row[3]),
                "mean_betrag": row[4],
                "std_betrag": row[5],
                "z_score": row[6],
            }
        )
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


def run_test_round_dollar_payments(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    max_rows: int = 1000,
) -> dict[str, Any]:
    """Ejecuta TST-ROUND-DOLLAR-PAYMENTS y devuelve resultado estándar."""
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
            TRY_CAST("Betrag" AS DOUBLE) AS betrag,
            CASE
                WHEN ABS(TRY_CAST("Betrag" AS DOUBLE) - ROUND(TRY_CAST("Betrag" AS DOUBLE), 0)) < 1e-9
                    THEN TRUE
                ELSE FALSE
            END AS is_round_amount
        FROM {qualified_table}
        WHERE TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
          AND ABS(TRY_CAST("Betrag" AS DOUBLE) - ROUND(TRY_CAST("Betrag" AS DOUBLE), 0)) < 1e-9
        ORDER BY betrag DESC, kreditor, belegnummer
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = ["kreditor", "belegnummer", "betrag", "is_round_amount"]
    rows = [
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "belegnummer": str(base["belegnummer"]),
                        "betrag": str(base["betrag"]),
                    },
                    evidence_columns=["kreditor", "belegnummer", "betrag", "is_round_amount"],
                    metrics={"is_round_amount": bool(base["is_round_amount"])},
                ),
            }
        )(
            {
                "kreditor": row[0],
                "belegnummer": row[1],
                "betrag": row[2],
                "is_round_amount": bool(row[3]),
            }
        )
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


def run_test_just_below_auth_threshold(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    threshold_values: tuple[float, ...] = (100.0, 500.0, 1000.0, 5000.0, 10000.0),
    threshold_band: float = 0.02,
    max_rows: int = 1000,
) -> dict[str, Any]:
    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    quoted_schema = _quote_identifier(schema_name)
    quoted_table = _quote_identifier(table_name)
    qualified_table = f"{quoted_schema}.{quoted_table}"
    executed_on = f"{schema_name}.{table_name}"

    threshold_sql = ", ".join(f"({float(value)})" for value in threshold_values)
    lower_factor = 1.0 - float(threshold_band)

    query = f"""
        WITH thresholds AS (
            SELECT * FROM (VALUES {threshold_sql}) t(threshold_value)
        ),
        base AS (
            SELECT
                "Kreditor" AS kreditor,
                "Belegnummer" AS belegnummer,
                TRY_CAST("Betrag" AS DOUBLE) AS betrag
            FROM {qualified_table}
            WHERE TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
        ),
        matches AS (
            SELECT
                b.kreditor,
                b.belegnummer,
                b.betrag,
                t.threshold_value AS threshold,
                (t.threshold_value - b.betrag) AS threshold_gap,
                ROW_NUMBER() OVER (
                    PARTITION BY b.kreditor, b.belegnummer, b.betrag
                    ORDER BY t.threshold_value
                ) AS rn
            FROM base b
            JOIN thresholds t
              ON b.betrag < t.threshold_value
             AND b.betrag >= t.threshold_value * {lower_factor}
        )
        SELECT
            kreditor,
            belegnummer,
            betrag,
            threshold,
            threshold_gap
        FROM matches
        WHERE rn = 1
        ORDER BY threshold_gap ASC, betrag DESC, kreditor, belegnummer
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = ["kreditor", "belegnummer", "betrag", "threshold", "threshold_gap"]
    rows = [
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "belegnummer": str(base["belegnummer"]),
                        "betrag": str(base["betrag"]),
                    },
                    evidence_columns=["kreditor", "belegnummer", "betrag", "threshold", "threshold_gap"],
                    metrics={
                        "threshold": float(base["threshold"]) if base["threshold"] is not None else None,
                        "threshold_gap": float(base["threshold_gap"])
                        if base["threshold_gap"] is not None
                        else None,
                    },
                ),
            }
        )(
            {
                "kreditor": row[0],
                "belegnummer": row[1],
                "betrag": row[2],
                "threshold": row[3],
                "threshold_gap": row[4],
            }
        )
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


def run_test_split_payments_near_limit(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    threshold: float = 1000.0,
    max_rows: int = 1000,
) -> dict[str, Any]:
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
                "Belegnummer" AS belegnummer,
                "Position" AS position,
                TRY_CAST("Betrag" AS DOUBLE) AS betrag
            FROM {qualified_table}
            WHERE "Kreditor" IS NOT NULL
              AND "Belegnummer" IS NOT NULL
              AND TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
        ),
        agg AS (
            SELECT
                kreditor,
                belegnummer,
                COUNT(*) AS line_count,
                SUM(betrag) AS total_betrag,
                MAX(betrag) AS max_line_betrag
            FROM base
            GROUP BY 1, 2
        )
        SELECT
            kreditor,
            belegnummer,
            line_count,
            total_betrag,
            max_line_betrag,
            ? AS threshold
        FROM agg
        WHERE line_count > 1
          AND max_line_betrag < ?
          AND total_betrag >= ?
        ORDER BY total_betrag DESC, line_count DESC, kreditor, belegnummer
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [threshold, threshold, threshold, max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = ["kreditor", "belegnummer", "line_count", "total_betrag", "max_line_betrag", "threshold"]
    rows = [
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "belegnummer": str(base["belegnummer"]),
                    },
                    evidence_columns=columns,
                    metrics={
                        "line_count": int(base["line_count"]),
                        "total_betrag": float(base["total_betrag"]),
                        "max_line_betrag": float(base["max_line_betrag"]),
                        "threshold": float(base["threshold"]),
                    },
                ),
            }
        )(
            {
                "kreditor": row[0],
                "belegnummer": row[1],
                "line_count": int(row[2]),
                "total_betrag": row[3],
                "max_line_betrag": row[4],
                "threshold": row[5],
            }
        )
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


def run_test_invoice_sequence_gaps(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    min_sequence_gap: int = 10,
    max_rows: int = 1000,
) -> dict[str, Any]:
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
            SELECT DISTINCT
                "Kreditor" AS kreditor,
                TRY_CAST(REGEXP_REPLACE(CAST("Belegnummer" AS VARCHAR), '\\.0+$', '') AS BIGINT) AS belegnummer_num,
                REGEXP_REPLACE(CAST("Belegnummer" AS VARCHAR), '\\.0+$', '') AS belegnummer
            FROM {qualified_table}
            WHERE "Kreditor" IS NOT NULL
              AND TRY_CAST(REGEXP_REPLACE(CAST("Belegnummer" AS VARCHAR), '\\.0+$', '') AS BIGINT) IS NOT NULL
        ),
        with_prev AS (
            SELECT
                kreditor,
                belegnummer,
                belegnummer_num,
                LAG(belegnummer_num) OVER (PARTITION BY kreditor ORDER BY belegnummer_num) AS previous_belegnummer_num
            FROM base
        )
        SELECT
            kreditor,
            belegnummer,
            CAST(previous_belegnummer_num AS VARCHAR) AS previous_belegnummer,
            (belegnummer_num - previous_belegnummer_num) AS sequence_gap
        FROM with_prev
        WHERE previous_belegnummer_num IS NOT NULL
          AND (belegnummer_num - previous_belegnummer_num) >= ?
        ORDER BY sequence_gap DESC, kreditor, belegnummer_num
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [min_sequence_gap, max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = ["kreditor", "belegnummer", "previous_belegnummer", "sequence_gap"]
    rows = [
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "belegnummer": str(base["belegnummer"]),
                    },
                    evidence_columns=columns,
                    metrics={"sequence_gap": int(base["sequence_gap"])},
                ),
            }
        )(
            {
                "kreditor": row[0],
                "belegnummer": row[1],
                "previous_belegnummer": row[2],
                "sequence_gap": int(row[3]),
            }
        )
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


def run_test_negative_quantity_receipts(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    max_rows: int = 1000,
) -> dict[str, Any]:
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
            "Material" AS material,
            TRY_CAST("Menge" AS DOUBLE) AS menge
        FROM {qualified_table}
        WHERE TRY_CAST("Menge" AS DOUBLE) < 0
        ORDER BY menge ASC, kreditor, belegnummer
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = ["kreditor", "belegnummer", "material", "menge"]
    rows = [
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "belegnummer": str(base["belegnummer"]),
                        "material": str(base["material"]),
                    },
                    evidence_columns=columns,
                    metrics={"menge": float(base["menge"]) if base["menge"] is not None else None},
                ),
            }
        )(
            {
                "kreditor": row[0],
                "belegnummer": row[1],
                "material": row[2],
                "menge": row[3],
            }
        )
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


def run_test_duplicate_material_items(
    test_spec: dict[str, Any],
    *,
    table_name: str = "fraud_1",
    schema_name: str = "main",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    max_rows: int = 1000,
) -> dict[str, Any]:
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
            "Material" AS material,
            COUNT(*) AS duplicate_count
        FROM {qualified_table}
        WHERE "Material" IS NOT NULL
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, kreditor, belegnummer, position, material
        LIMIT ?
    """

    started = perf_counter()
    try:
        raw_rows = conn.execute(query, [max_rows]).fetchall()
    finally:
        if own_connection:
            conn.close()
    duration_ms = int((perf_counter() - started) * 1000)

    columns = ["kreditor", "belegnummer", "position", "material", "duplicate_count"]
    rows = [
        (
            lambda base: {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys={
                        "kreditor": str(base["kreditor"]),
                        "belegnummer": str(base["belegnummer"]),
                        "position": str(base["position"]),
                        "material": str(base["material"]),
                    },
                    evidence_columns=columns,
                    metrics={"duplicate_count": int(base["duplicate_count"])},
                ),
            }
        )(
            {
                "kreditor": row[0],
                "belegnummer": row[1],
                "position": row[2],
                "material": row[3],
                "duplicate_count": int(row[4]),
            }
        )
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


def run_test_sql_ref_generic(
    test_spec: dict[str, Any],
    *,
    schema_name: str = "main",
    table_name: str = "fraud_1",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
) -> dict[str, Any]:
    """Ejecutor SQL genérico para tests de catálogo con `logic.sql_ref`."""
    logic = test_spec.get("logic", {})
    if not isinstance(logic, dict):
        raise ValueError("logic debe ser objeto")
    sql_ref = str(logic.get("sql_ref", "")).strip()
    if not sql_ref:
        raise ValueError(f"{test_spec.get('id', '')}: falta logic.sql_ref para ejecución SQL genérica")

    sql_path = _resolve_sql_ref_path(test_spec=test_spec, sql_ref=sql_ref)
    query = sql_path.read_text(encoding="utf-8")

    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None

    started = perf_counter()
    cur = conn.execute(query)
    raw_rows = cur.fetchall()
    columns = [str(col[0]).strip() for col in (cur.description or [])]
    duration_ms = int((perf_counter() - started) * 1000)

    expected_output = test_spec.get("expected_output", {})
    finding_fields = []
    if isinstance(expected_output, dict):
        finding_fields = expected_output.get("finding_fields", [])
    preferred_key_fields = [str(name).strip() for name in finding_fields if str(name).strip()]
    evidence_columns = [str(col).strip().lower() for col in test_spec.get("evidence_columns", []) if str(col).strip()]

    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        base = {
            columns[idx]: row[idx]
            for idx in range(min(len(columns), len(row)))
            if columns[idx]
        }
        keys: dict[str, str] = {}
        for key_name in preferred_key_fields:
            if key_name in base and base[key_name] is not None:
                keys[key_name] = str(base[key_name])
            if len(keys) >= 4:
                break
        if not keys and base:
            first_key = next(iter(base.keys()))
            keys[first_key] = str(base[first_key])
        metric_payload = {
            key: value
            for key, value in base.items()
            if key not in keys
        }
        rows.append(
            {
                **base,
                **_build_finding_common_fields(
                    test_id=str(test_spec.get("id", "")),
                    keys=keys,
                    evidence_columns=evidence_columns or list(base.keys()),
                    metrics=metric_payload,
                ),
            }
        )

    result = build_standard_test_result(
        test_spec=test_spec,
        status="OK",
        rows=rows,
        columns=columns,
        duration_ms=duration_ms,
        implementation_type="sql_ref",
        executed_on=f"{schema_name}.{table_name}",
    )
    try:
        return _annotate_o2c_discount_applicability(
            test_spec=test_spec,
            result=result,
            conn=conn,
            schema_name=schema_name,
        )
    finally:
        if own_connection:
            conn.close()
