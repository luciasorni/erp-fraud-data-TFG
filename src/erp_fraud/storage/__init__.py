"""Storage backends and persistence helpers."""

from .duckdb_store import (
    DEFAULT_DUCKDB_PATH,
    TableLoadStats,
    create_db_if_missing,
    get_duckdb_connection,
    load_table_to_duckdb,
    load_table_to_duckdb_with_stats,
)
from .paths import RUTA_SALIDA, ruta_run

__all__ = [
    "DEFAULT_DUCKDB_PATH",
    "RUTA_SALIDA",
    "TableLoadStats",
    "create_db_if_missing",
    "get_duckdb_connection",
    "load_table_to_duckdb",
    "load_table_to_duckdb_with_stats",
    "ruta_run",
]
