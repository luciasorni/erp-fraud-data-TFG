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
from .json_logging import DEFAULT_INGEST_LOG_FILENAME, IngestJsonLogger
from .run_metadata import build_run_metadata, write_run_metadata_json
from .schema_summary import build_schema_summary, write_schema_summary_json

__all__ = [
    "DEFAULT_DUCKDB_PATH",
    "DEFAULT_INGEST_LOG_FILENAME",
    "RUTA_SALIDA",
    "IngestJsonLogger",
    "TableLoadStats",
    "build_run_metadata",
    "build_schema_summary",
    "create_db_if_missing",
    "get_duckdb_connection",
    "load_table_to_duckdb",
    "load_table_to_duckdb_with_stats",
    "ruta_run",
    "write_run_metadata_json",
    "write_schema_summary_json",
]
