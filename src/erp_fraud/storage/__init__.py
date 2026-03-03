"""Storage backends and persistence helpers."""

from .data_dictionary import (
    DataDictionaryCompletenessError,
    annotate_dictionary_from_tests,
    build_data_dictionary_draft_from_schema_summary,
    check_dictionary_completeness,
    ensure_min_fields_in_data_dictionary,
    generate_data_dictionary_json_draft,
    load_test_specs_from_catalog,
    normalize_data_dictionary_entry_min_fields,
)
from .paths import RUTA_SALIDA, ruta_run
from .json_logging import DEFAULT_INGEST_LOG_FILENAME, IngestJsonLogger
from .run_metadata import build_run_metadata, write_run_metadata_json

__all__ = [
    "DEFAULT_INGEST_LOG_FILENAME",
    "RUTA_SALIDA",
    "DataDictionaryCompletenessError",
    "IngestJsonLogger",
    "annotate_dictionary_from_tests",
    "build_data_dictionary_draft_from_schema_summary",
    "build_run_metadata",
    "check_dictionary_completeness",
    "ensure_min_fields_in_data_dictionary",
    "generate_data_dictionary_json_draft",
    "load_test_specs_from_catalog",
    "normalize_data_dictionary_entry_min_fields",
    "ruta_run",
    "write_run_metadata_json",
]

try:
    from .duckdb_store import (
        DEFAULT_DUCKDB_PATH,
        TableLoadStats,
        create_db_if_missing,
        get_duckdb_connection,
        load_table_to_duckdb,
        load_table_to_duckdb_with_stats,
    )

    __all__.extend(
        [
            "DEFAULT_DUCKDB_PATH",
            "TableLoadStats",
            "create_db_if_missing",
            "get_duckdb_connection",
            "load_table_to_duckdb",
            "load_table_to_duckdb_with_stats",
        ]
    )
except ModuleNotFoundError:
    # Permite usar módulos de storage no dependientes de DuckDB (p.ej. CLI dictionary)
    pass

try:
    from .schema_summary import build_schema_summary, write_schema_summary_json

    __all__.extend(
        [
            "build_schema_summary",
            "write_schema_summary_json",
        ]
    )
except ModuleNotFoundError:
    pass
