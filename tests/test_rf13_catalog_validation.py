from __future__ import annotations

from pathlib import Path

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
        "red_flag_id": "RF-P2P-001",
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


def _write_red_flags_mapping(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "version: 1.0.0",
                "red_flags:",
                "  - red_flag_id: RF-P2P-001",
                "    fraud_type: duplicate_payment",
                "  - red_flag_id: RF-P2P-002",
                "    fraud_type: amount_anomaly",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_validate_catalog_against_schema_summary_accepts_valid_spec(tmp_path: Path) -> None:
    mapping_path = tmp_path / "red_flags_mapping.yaml"
    _write_red_flags_mapping(mapping_path)
    validate_catalog_against_schema_summary(
        test_specs=[_valid_spec()],
        schema_summary_payload=_schema_summary(),
        red_flags_mapping_path=mapping_path,
    )


def test_validate_catalog_against_schema_summary_rejects_missing_rf13_fields(tmp_path: Path) -> None:
    mapping_path = tmp_path / "red_flags_mapping.yaml"
    _write_red_flags_mapping(mapping_path)
    bad = _valid_spec()
    bad.pop("process_step")
    with pytest.raises(CatalogValidationError, match="faltan campos obligatorios RF13"):
        validate_catalog_against_schema_summary(
            test_specs=[bad],
            schema_summary_payload=_schema_summary(),
            red_flags_mapping_path=mapping_path,
        )


def test_validate_catalog_against_schema_summary_rejects_missing_evidence_column_in_schema(
    tmp_path: Path,
) -> None:
    mapping_path = tmp_path / "red_flags_mapping.yaml"
    _write_red_flags_mapping(mapping_path)
    bad = _valid_spec()
    bad["evidence_columns"] = ["Kreditor", "NoExiste"]
    with pytest.raises(CatalogValidationError, match="evidence_column 'NoExiste'"):
        validate_catalog_against_schema_summary(
            test_specs=[bad],
            schema_summary_payload=_schema_summary(),
            red_flags_mapping_path=mapping_path,
        )


def test_validate_catalog_against_schema_summary_rejects_unknown_red_flag_id(tmp_path: Path) -> None:
    mapping_path = tmp_path / "red_flags_mapping.yaml"
    _write_red_flags_mapping(mapping_path)
    bad = _valid_spec()
    bad["red_flag_id"] = "RF-P2P-999"
    with pytest.raises(CatalogValidationError, match="no existe en mapping"):
        validate_catalog_against_schema_summary(
            test_specs=[bad],
            schema_summary_payload=_schema_summary(),
            red_flags_mapping_path=mapping_path,
        )


def test_validate_catalog_against_schema_summary_rejects_mismatched_fraud_type(
    tmp_path: Path,
) -> None:
    mapping_path = tmp_path / "red_flags_mapping.yaml"
    _write_red_flags_mapping(mapping_path)
    bad = _valid_spec()
    bad["fraud_type"] = "amount_anomaly"
    with pytest.raises(CatalogValidationError, match="incoherente con fraud_type"):
        validate_catalog_against_schema_summary(
            test_specs=[bad],
            schema_summary_payload=_schema_summary(),
            red_flags_mapping_path=mapping_path,
        )
