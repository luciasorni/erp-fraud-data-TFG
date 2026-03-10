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
from .data_validation_policy import (
    VALIDATION_SEVERITY_POLICY,
    ValidationRule,
    get_validation_policy_dict,
    get_validation_severity,
    is_critical_check,
)
from .data_validation_requirements import extract_required_columns_from_testspecs
from .data_validation_checks import (
    check_basic_ranges_in_duckdb,
    check_missing_required_columns_in_duckdb,
    check_null_percentage_required_columns_in_duckdb,
    check_type_parse_errors_in_duckdb,
)
from .data_validation_report import build_data_validation_report, write_data_validation_report_json
from .data_validation_pipeline import (
    TechnicalValidationOutcome,
    run_technical_validation_before_tests,
)
from .paths import RUTA_SALIDA, ruta_run
from .json_logging import DEFAULT_INGEST_LOG_FILENAME, IngestJsonLogger
from .run_metadata import build_run_metadata, write_run_metadata_json
from .reporting import write_or_update_report_markdown_with_data_validation
from .reporting import write_or_update_report_markdown_with_drilldown_instructions
from .reporting import build_report_markdown_template, write_report_markdown_template
from .reporting import (
    build_report_markdown_from_report_json_payload,
    render_report_markdown_to_html,
    write_report_markdown_from_report_json,
)
from .report_json import (
    REPORT_JSON_VERSION,
    build_default_report_artifact_paths,
    build_report_json_payload,
    validate_report_artifact_paths_exist,
    validate_report_json_file_artifact_links,
    write_report_json,
)

__all__ = [
    "DEFAULT_INGEST_LOG_FILENAME",
    "RUTA_SALIDA",
    "DataDictionaryCompletenessError",
    "IngestJsonLogger",
    "TechnicalValidationOutcome",
    "VALIDATION_SEVERITY_POLICY",
    "annotate_dictionary_from_tests",
    "build_data_dictionary_draft_from_schema_summary",
    "build_data_validation_report",
    "build_run_metadata",
    "check_dictionary_completeness",
    "check_basic_ranges_in_duckdb",
    "check_missing_required_columns_in_duckdb",
    "check_null_percentage_required_columns_in_duckdb",
    "check_type_parse_errors_in_duckdb",
    "ensure_min_fields_in_data_dictionary",
    "generate_data_dictionary_json_draft",
    "extract_required_columns_from_testspecs",
    "get_validation_policy_dict",
    "get_validation_severity",
    "load_test_specs_from_catalog",
    "is_critical_check",
    "normalize_data_dictionary_entry_min_fields",
    "run_technical_validation_before_tests",
    "REPORT_JSON_VERSION",
    "build_report_markdown_template",
    "build_report_markdown_from_report_json_payload",
    "render_report_markdown_to_html",
    "ValidationRule",
    "build_report_json_payload",
    "build_default_report_artifact_paths",
    "validate_report_artifact_paths_exist",
    "validate_report_json_file_artifact_links",
    "ruta_run",
    "write_report_json",
    "write_run_metadata_json",
    "write_or_update_report_markdown_with_data_validation",
    "write_or_update_report_markdown_with_drilldown_instructions",
    "write_report_markdown_from_report_json",
    "write_report_markdown_template",
    "write_data_validation_report_json",
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
