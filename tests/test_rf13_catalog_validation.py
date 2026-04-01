from __future__ import annotations

import pytest

from src.erp_fraud.catalog import CatalogValidationError, validate_catalog_against_schema_summary


def _schema_summary() -> dict:
    return {
        "schema_name": "main",
        "table_count": 1,
        "tables": [
            {
                "table_name": "fraud_1",
                "columns": [
                    {"name": "Kreditor", "type": "VARCHAR"},
                    {"name": "Belegnummer", "type": "VARCHAR"},
                    {"name": "Betrag", "type": "DOUBLE"},
                    {"name": "Transaktionsart", "type": "VARCHAR"},
                ],
            }
        ],
    }


def _valid_spec() -> dict:
    return {
        "id": "TST-OK",
        "fraud_type": "duplicate_payment",
        "process_step": "invoice_posting",
        "expected_output": {"primary_entity": "invoice_line", "finding_fields": ["kreditor"]},
        "evidence_columns": ["Kreditor", "Betrag"],
        "data_requirements": {
            "tables": [
                {
                    "table": "fraud_1",
                    "required_columns": ["Kreditor", "Betrag"],
                }
            ]
        },
    }


def test_validate_catalog_against_schema_summary_accepts_valid_spec() -> None:
    validate_catalog_against_schema_summary(
        test_specs=[_valid_spec()],
        schema_summary_payload=_schema_summary(),
    )


def test_validate_catalog_against_schema_summary_rejects_missing_rf13_fields() -> None:
    bad = _valid_spec()
    bad.pop("process_step")
    with pytest.raises(CatalogValidationError, match="faltan campos obligatorios RF13"):
        validate_catalog_against_schema_summary(
            test_specs=[bad],
            schema_summary_payload=_schema_summary(),
        )


def test_validate_catalog_against_schema_summary_rejects_missing_evidence_column_in_schema() -> None:
    bad = _valid_spec()
    bad["evidence_columns"] = ["Kreditor", "NoExiste"]
    with pytest.raises(CatalogValidationError, match="evidence_column 'NoExiste'"):
        validate_catalog_against_schema_summary(
            test_specs=[bad],
            schema_summary_payload=_schema_summary(),
        )
