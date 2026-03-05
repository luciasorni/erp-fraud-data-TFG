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
from .test_execution import (
    STANDARD_TEST_RESULT_SCHEMA_VERSION,
    build_standard_test_result,
    run_test_duplicate_postings,
    run_test_unusual_amount_by_vendor,
)
from .test_runner import TestRunner

__all__ = [
    "TEST_SPEC_SCHEMA_VERSION",
    "TEST_SPEC_SCHEMA",
    "get_test_spec_schema",
    "get_test_spec_required_fields",
    "SUPPORTED_TESTSPEC_SUFFIXES",
    "STANDARD_TEST_RESULT_SCHEMA_VERSION",
    "TestSpecValidationError",
    "build_standard_test_result",
    "load_test_specs_from_catalog",
    "run_test_duplicate_postings",
    "run_test_unusual_amount_by_vendor",
    "TestRunner",
    "validate_test_spec",
]
