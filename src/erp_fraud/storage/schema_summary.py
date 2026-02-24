"""Generación de resumen de esquema desde DuckDB."""

from __future__ import annotations

from pathlib import Path
import json

import duckdb

from .duckdb_store import DEFAULT_DUCKDB_PATH, get_duckdb_connection


def build_schema_summary(
    *,
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    schema_name: str = "main",
) -> dict:
    """Construye un resumen de esquema estable/ordenado desde DuckDB."""
    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)

    assert conn is not None
    try:
        rows = conn.execute(
            """
            SELECT
                table_schema,
                table_name,
                column_name,
                data_type,
                is_nullable,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = ?
            ORDER BY table_schema, table_name, ordinal_position
            """,
            [schema_name],
        ).fetchall()
    finally:
        if own_connection:
            conn.close()

    tables: dict[str, dict] = {}
    for table_schema, table_name, column_name, data_type, is_nullable, ordinal_position in rows:
        key = f"{table_schema}.{table_name}"
        if key not in tables:
            tables[key] = {
                "table_schema": table_schema,
                "table_name": table_name,
                "columns": [],
            }
        tables[key]["columns"].append(
            {
                "name": column_name,
                "type": data_type,
                "nullable": is_nullable == "YES",
                "ordinal_position": int(ordinal_position),
            }
        )

    ordered_tables = [tables[key] for key in sorted(tables.keys())]
    return {
        "schema_name": schema_name,
        "table_count": len(ordered_tables),
        "tables": ordered_tables,
    }


def write_schema_summary_json(
    output_path: str | Path,
    *,
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    schema_name: str = "main",
) -> Path:
    """Genera `schema_summary.json` con serialización estable."""
    summary = build_schema_summary(conn=conn, db_path=db_path, schema_name=schema_name)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
