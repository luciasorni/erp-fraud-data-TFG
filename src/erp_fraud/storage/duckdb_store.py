"""Helpers de conexión y creación de base de datos DuckDB local."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import duckdb
import pandas as pd


DEFAULT_DUCKDB_PATH = Path("erp.duckdb")


@dataclass(frozen=True)
class TableLoadStats:
    """Métricas de carga por tabla."""

    table_name: str
    mode: str
    rows_loaded: int
    duration_ms: int


def create_db_if_missing(db_path: str | Path = DEFAULT_DUCKDB_PATH) -> Path:
    """Crea el fichero DuckDB si no existe y devuelve su ruta."""
    path = Path(db_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    # Abrir/cerrar fuerza la creación del fichero si no existe.
    conn = duckdb.connect(str(path))
    conn.close()
    return path


def get_duckdb_connection(db_path: str | Path = DEFAULT_DUCKDB_PATH) -> duckdb.DuckDBPyConnection: # get_duckdb_connection es una función que devuelve una conexión a una base de datos DuckDB local, creando el fichero de la base de datos si no existe.
    """Devuelve una conexión DuckDB local, creando el fichero si falta."""
    path = create_db_if_missing(db_path)
    return duckdb.connect(str(path))


def _quote_identifier(identifier: str) -> str:
    if not identifier or not identifier.strip():
        raise ValueError("table_name debe ser un string no vacío")
    return '"' + identifier.strip().replace('"', '""') + '"'


def load_table_to_duckdb(
    table_name: str,
    df: pd.DataFrame,
    *,
    mode: str = "overwrite",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
) -> int:
    """Carga un DataFrame en DuckDB con modo overwrite/append.

    - `overwrite`: reemplaza la tabla completa.
    - `append`: inserta filas; si la tabla no existe, la crea con el esquema del DataFrame.

    Devuelve el número de filas cargadas.
    """
    if mode not in {"overwrite", "append"}:
        raise ValueError("mode debe ser 'overwrite' o 'append'")
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df debe ser un pandas.DataFrame")

    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)

    assert conn is not None
    quoted_table = _quote_identifier(table_name)
    temp_view = "__erp_fraud_load_df"

    try:
        conn.register(temp_view, df)
        if mode == "overwrite":
            conn.execute(f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM {temp_view}")
        else:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {quoted_table} AS "
                f"SELECT * FROM {temp_view} LIMIT 0"
            )
            conn.execute(f"INSERT INTO {quoted_table} SELECT * FROM {temp_view}")
    finally:
        try:
            conn.unregister(temp_view)
        except Exception:
            pass
        if own_connection:
            conn.close()

    return int(len(df))


def load_table_to_duckdb_with_stats(
    table_name: str,
    df: pd.DataFrame,
    *,
    mode: str = "overwrite",
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
) -> TableLoadStats:
    """Carga una tabla y devuelve métricas de filas y duración."""
    started = perf_counter()
    rows_loaded = load_table_to_duckdb(
        table_name,
        df,
        mode=mode,
        conn=conn,
        db_path=db_path,
    )
    duration_ms = int((perf_counter() - started) * 1000)
    return TableLoadStats(
        table_name=table_name,
        mode=mode,
        rows_loaded=rows_loaded,
        duration_ms=duration_ms,
    )
