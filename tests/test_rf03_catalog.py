from __future__ import annotations

import duckdb
import pytest

from src.erp_fraud.catalog import (
    STANDARD_TEST_RESULT_SCHEMA_VERSION,
    load_test_specs_from_catalog,
    run_test_duplicate_postings,
    run_test_unusual_amount_by_vendor,
    validate_test_spec,
)
from src.erp_fraud.catalog.test_spec_loader import TestSpecValidationError as CatalogSpecValidationError


def _spec_by_id(catalog_specs: list[dict], test_id: str) -> dict:
    for spec in catalog_specs:
        if spec.get("id") == test_id:
            return spec
    raise AssertionError(f"No se encontró TestSpec: {test_id}")


def test_catalog_loads_two_valid_specs() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    ids = sorted(str(spec.get("id")) for spec in specs)
    assert ids == ["TST-DUPLICATE-POSTINGS", "TST-UNUSUAL-AMOUNT-BY-VENDOR"]
    for spec in specs:
        assert isinstance(spec.get("process_step"), str)
        assert isinstance(spec.get("expected_output"), dict)
        assert isinstance(spec.get("evidence_columns"), list)


def test_validate_test_spec_rejects_inconsistent_required_columns_exact() -> None:
    bad_spec = {
        "id": "TST-BAD-EXACT",
        "version": "1.0.0",
        "name": "Bad exact columns",
        "fraud_type": "quality",
        "process_step": "invoice_posting",
        "description": "Invalid spec for testing",
        "source": {"catalog": "acfe_coso", "reference": "dummy"},
        "data_requirements": {
            "tables": [
                {
                    "table": "fraud_1",
                    "required_columns": ["A", "B"],
                    "required_columns_exact": ["A"],
                }
            ]
        },
        "expected_output": {"primary_entity": "invoice_line", "finding_fields": ["kreditor"]},
        "evidence_columns": ["Kreditor"],
        "logic": {"implementation_type": "sql"},
    }
    with pytest.raises(CatalogSpecValidationError, match="required_columns_exact"):
        validate_test_spec(bad_spec)


def test_validate_test_spec_rejects_missing_new_required_fields() -> None:
    bad_spec = {
        "id": "TST-MISSING-NEW-FIELDS",
        "version": "1.0.0",
        "name": "Missing process metadata",
        "fraud_type": "quality",
        "description": "Invalid spec for testing",
        "source": {"catalog": "acfe_coso", "reference": "dummy"},
        "data_requirements": {
            "tables": [{"table": "fraud_1", "required_columns": ["A"]}],
        },
        "logic": {"implementation_type": "sql"},
    }
    with pytest.raises(CatalogSpecValidationError, match="faltan campos obligatorios"):
        validate_test_spec(bad_spec)


def test_run_test_duplicate_postings_returns_standard_result() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-DUPLICATE-POSTINGS")

    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE fraud_1 (Kreditor VARCHAR, Belegnummer VARCHAR, Position VARCHAR, Betrag DOUBLE, Transaktionsart VARCHAR)"
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?)",
        [
            ("V1", "D1", "10", 100.0, "N"),
            ("V1", "D1", "10", 100.0, "N"),
            ("V2", "D2", "20", 200.0, "N"),
        ],
    )

    out = run_test_duplicate_postings(spec, conn=conn, table_name="fraud_1", schema_name="main")
    conn.close()

    assert out["result_schema_version"] == STANDARD_TEST_RESULT_SCHEMA_VERSION
    assert out["test_id"] == "TST-DUPLICATE-POSTINGS"
    assert out["status"] == "OK"
    assert out["finding_count"] == 1
    assert out["columns"] == ["kreditor", "belegnummer", "position", "betrag", "duplicate_count"]
    assert out["rows"][0]["kreditor"] == "V1"
    assert out["rows"][0]["duplicate_count"] == 2


def test_run_test_unusual_amount_by_vendor_returns_standard_result() -> None:
    specs = load_test_specs_from_catalog("tests/catalog", validate_schema=True)
    spec = _spec_by_id(specs, "TST-UNUSUAL-AMOUNT-BY-VENDOR")

    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE fraud_1 (Kreditor VARCHAR, Belegnummer VARCHAR, Position VARCHAR, Betrag DOUBLE, Transaktionsart VARCHAR)"
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?)",
        [
            ("V1", "D1", "10", 100.0, "N"),
            ("V1", "D2", "10", 101.0, "N"),
            ("V1", "D3", "10", 99.0, "N"),
            ("V1", "D4", "10", 100.0, "N"),
            ("V1", "D5", "10", 500.0, "N"),
            ("V2", "D6", "10", 10.0, "N"),
            ("V2", "D7", "10", 11.0, "N"),
        ],
    )

    out = run_test_unusual_amount_by_vendor(
        spec,
        conn=conn,
        table_name="fraud_1",
        schema_name="main",
        min_rows_per_vendor=5,
        z_threshold=1.7,
    )
    conn.close()

    assert out["result_schema_version"] == STANDARD_TEST_RESULT_SCHEMA_VERSION
    assert out["test_id"] == "TST-UNUSUAL-AMOUNT-BY-VENDOR"
    assert out["status"] == "OK"
    assert out["finding_count"] >= 1
    assert out["columns"] == [
        "kreditor",
        "transaktionsart",
        "betrag",
        "n_rows",
        "mean_betrag",
        "std_betrag",
        "z_score",
    ]
    assert out["rows"][0]["kreditor"] == "V1"
    assert out["rows"][0]["z_score"] >= 1.7
