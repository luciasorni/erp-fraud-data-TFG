"""Catálogo de tests de fraude (RF03+)."""

from .test_spec_schema import (
    TEST_SPEC_SCHEMA_VERSION,
    TEST_SPEC_SCHEMA,
    get_test_spec_schema,
    get_test_spec_required_fields,
)
from .test_spec_loader import (
    SUPPORTED_TESTSPEC_SUFFIXES,
    TestSpecValidationError,
    load_test_specs_from_catalog,
    validate_test_spec,
)
from .catalog_validation import (
    CatalogValidationError,
    REQUIRED_TESTSPEC_FIELDS_RF13,
    validate_catalog_against_schema_summary,
)
from .test_execution import (
    STANDARD_TEST_RESULT_SCHEMA_VERSION,
    build_standard_test_result,
    run_test_duplicate_material_items,
    run_test_duplicate_postings,
    run_test_invoice_sequence_gaps,
    run_test_just_below_auth_threshold,
    run_test_negative_quantity_receipts,
    run_test_round_dollar_payments,
    run_test_split_payments_near_limit,
    run_test_unusual_amount_by_vendor,
)
from .result_schema import (
    RESULT_SCHEMA,
    RESULT_SCHEMA_EXTENDED_FIELDS,
    RESULT_SCHEMA_FIELD_TYPES,
    RESULT_SCHEMA_REQUIRED_FIELDS,
    RESULT_SCHEMA_VERSION,
    get_result_schema,
    get_result_schema_required_fields,
)
from .result_schema_validator import RESULT_DF_REQUIRED_COLUMNS, validate_result_schema
from .entity_key import (
    ENTITY_KEY_ASSIGN_SEPARATOR,
    ENTITY_KEY_SEPARATOR,
    build_entity_key,
    parse_entity_key,
)
from .result_writer import (
    sort_result_rows_stable,
    write_test_result_jsonl,
    write_test_result_parquet,
    write_test_results_by_test_id,
)
from .drilldown_keys import (
    DRILLDOWN_MIN_KEYS_BY_TEST_ID,
    get_drilldown_min_keys_by_test_id,
    get_minimum_keys_for_test_id,
    validate_minimum_keys_for_test_id,
)
from .drilldown_templates import (
    DRILLDOWN_QUERY_ID_BY_TEST_ID,
    build_drilldown_template_ref,
    get_drilldown_query_id_for_test_id,
)
from .drilldown import drilldown
from .scoring import (
    compute_score_test,
    extract_metric_value,
    load_weights_config,
    resolve_ranking_top_k,
    resolve_test_weight,
)
from .ranking import aggregate_findings_by_entity
from .ranking_writer import (
    sort_ranking_rows_stable,
    write_ranking_json,
    write_ranking_outputs,
    write_ranking_parquet,
)
from .test_runner import TestRunner

__all__ = [
    "TEST_SPEC_SCHEMA_VERSION",
    "TEST_SPEC_SCHEMA",
    "get_test_spec_schema",
    "get_test_spec_required_fields",
    "SUPPORTED_TESTSPEC_SUFFIXES",
    "STANDARD_TEST_RESULT_SCHEMA_VERSION",
    "RESULT_SCHEMA",
    "RESULT_SCHEMA_EXTENDED_FIELDS",
    "RESULT_SCHEMA_FIELD_TYPES",
    "RESULT_SCHEMA_REQUIRED_FIELDS",
    "RESULT_SCHEMA_VERSION",
    "RESULT_DF_REQUIRED_COLUMNS",
    "ENTITY_KEY_ASSIGN_SEPARATOR",
    "ENTITY_KEY_SEPARATOR",
    "DRILLDOWN_MIN_KEYS_BY_TEST_ID",
    "DRILLDOWN_QUERY_ID_BY_TEST_ID",
    "TestSpecValidationError",
    "CatalogValidationError",
    "REQUIRED_TESTSPEC_FIELDS_RF13",
    "build_standard_test_result",
    "build_drilldown_template_ref",
    "build_entity_key",
    "drilldown",
    "compute_score_test",
    "extract_metric_value",
    "load_weights_config",
    "resolve_ranking_top_k",
    "resolve_test_weight",
    "aggregate_findings_by_entity",
    "sort_ranking_rows_stable",
    "write_ranking_json",
    "write_ranking_outputs",
    "write_ranking_parquet",
    "get_result_schema",
    "get_result_schema_required_fields",
    "load_test_specs_from_catalog",
    "get_drilldown_min_keys_by_test_id",
    "get_drilldown_query_id_for_test_id",
    "get_minimum_keys_for_test_id",
    "sort_result_rows_stable",
    "validate_minimum_keys_for_test_id",
    "write_test_result_jsonl",
    "write_test_result_parquet",
    "write_test_results_by_test_id",
    "parse_entity_key",
    "run_test_duplicate_postings",
    "run_test_duplicate_material_items",
    "run_test_invoice_sequence_gaps",
    "run_test_just_below_auth_threshold",
    "run_test_negative_quantity_receipts",
    "run_test_round_dollar_payments",
    "run_test_split_payments_near_limit",
    "run_test_unusual_amount_by_vendor",
    "validate_catalog_against_schema_summary",
    "TestRunner",
    "validate_result_schema",
    "validate_test_spec",
]
