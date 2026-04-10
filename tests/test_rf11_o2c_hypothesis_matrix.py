from __future__ import annotations

import csv
import json
from pathlib import Path

from src.erp_fraud.storage.o2c_hypothesis_matrix import validate_o2c_hypothesis_matrix


def _write_matrix(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "hypothesis_id",
        "hypothesis_title",
        "process_step",
        "fraud_type",
        "test_id",
        "test_status",
        "evidence_entity",
        "evidence_columns",
        "business_key_fields",
        "source_deviation_id",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_catalog_spec(path: Path, *, test_id: str, fraud_type: str, process_step: str) -> None:
    payload = {
        "id": test_id,
        "version": "1.0.0",
        "name": "Synthetic O2C test",
        "fraud_type": fraud_type,
        "red_flag_id": "RF-O2C-999",
        "process_step": process_step,
        "description": "Synthetic catalog spec for matrix validation tests.",
        "source": {"catalog": "acfe_coso", "reference": "synthetic_case"},
        "data_requirements": {
            "tables": [
                {
                    "table": "o2c_order",
                    "required_columns": ["sales_order_id", "sales_order_item_id", "customer_id"],
                }
            ]
        },
        "expected_output": {
            "primary_entity": "sales_order_item",
            "finding_fields": ["sales_order_id", "sales_order_item_id", "customer_id"],
        },
        "evidence_columns": ["sales_order_id", "sales_order_item_id", "customer_id"],
        "logic": {"implementation_type": "python"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_rf11_11_validate_matrix_ok() -> None:
    payload = validate_o2c_hypothesis_matrix()
    assert payload["status"] == "OK"
    assert int(payload["rows_total"]) >= 1
    assert payload["rows_total"] == payload["rows_valid"]


def test_rf11_11_validate_matrix_detects_invalid_fields(tmp_path: Path) -> None:
    matrix_path = tmp_path / "bad_matrix.csv"
    _write_matrix(
        matrix_path,
        [
            {
                "hypothesis_id": "HYP-O2C-ERR",
                "hypothesis_title": "Bad row",
                "process_step": "sales_order",
                "fraud_type": "price_manipulation",
                "test_id": "TST-O2C-BAD",
                "test_status": "planned",
                "evidence_entity": "o2c_order",
                "evidence_columns": "sales_order_id;NO_FIELD",
                "business_key_fields": "sales_order_id;sales_order_item_id",
                "source_deviation_id": "O2C-07",
                "notes": "bad evidence",
            }
        ],
    )

    payload = validate_o2c_hypothesis_matrix(matrix_csv_path=matrix_path)
    assert payload["status"] == "ERROR"
    assert any("evidence_columns fuera de schema" in str(err) for err in payload["errors"])


def test_rf11_11_validate_matrix_detects_duplicate_hypothesis_test(tmp_path: Path) -> None:
    matrix_path = tmp_path / "dup_matrix.csv"
    row = {
        "hypothesis_id": "HYP-O2C-001",
        "hypothesis_title": "Dup",
        "process_step": "sales_order",
        "fraud_type": "price_manipulation",
        "test_id": "TST-O2C-PRICE-OUTLIER",
        "test_status": "planned",
        "evidence_entity": "o2c_order",
        "evidence_columns": "sales_order_id;sales_order_item_id;item_net_price",
        "business_key_fields": "sales_order_id;sales_order_item_id",
        "source_deviation_id": "O2C-07",
        "notes": "dup",
    }
    _write_matrix(matrix_path, [row, row])

    payload = validate_o2c_hypothesis_matrix(matrix_csv_path=matrix_path)
    assert payload["status"] == "ERROR"
    assert any("duplicado hypothesis_id+test_id" in str(err) for err in payload["errors"])


def test_rf11_11_validate_matrix_detects_missing_implemented_test_in_catalog(tmp_path: Path) -> None:
    matrix_path = tmp_path / "missing_catalog_test.csv"
    _write_matrix(
        matrix_path,
        [
            {
                "hypothesis_id": "HYP-O2C-001",
                "hypothesis_title": "Missing impl test",
                "process_step": "sales_order",
                "fraud_type": "price_manipulation",
                "test_id": "TST-O2C-MISSING",
                "test_status": "implemented",
                "evidence_entity": "o2c_order",
                "evidence_columns": "sales_order_id;sales_order_item_id;customer_id",
                "business_key_fields": "sales_order_id;sales_order_item_id",
                "source_deviation_id": "O2C-07",
                "notes": "missing",
            }
        ],
    )
    empty_catalog = tmp_path / "catalog_o2c"
    empty_catalog.mkdir(parents=True, exist_ok=True)
    payload = validate_o2c_hypothesis_matrix(
        matrix_csv_path=matrix_path,
        o2c_catalog_path=empty_catalog,
    )
    assert payload["status"] == "ERROR"
    assert any("implementado no existe en catálogo O2C" in str(err) for err in payload["errors"])


def test_rf11_11_validate_matrix_detects_catalog_mismatch_for_implemented_test(tmp_path: Path) -> None:
    matrix_path = tmp_path / "mismatch_catalog_test.csv"
    _write_matrix(
        matrix_path,
        [
            {
                "hypothesis_id": "HYP-O2C-002",
                "hypothesis_title": "Mismatch",
                "process_step": "sales_order",
                "fraud_type": "price_manipulation",
                "test_id": "TST-O2C-MISMATCH",
                "test_status": "implemented",
                "evidence_entity": "o2c_order",
                "evidence_columns": "sales_order_id;sales_order_item_id;customer_id",
                "business_key_fields": "sales_order_id;sales_order_item_id",
                "source_deviation_id": "O2C-07",
                "notes": "mismatch",
            }
        ],
    )
    catalog = tmp_path / "catalog_o2c"
    _write_catalog_spec(
        catalog / "tst_o2c_mismatch.json",
        test_id="TST-O2C-MISMATCH",
        fraud_type="discount_abuse",
        process_step="invoice",
    )
    payload = validate_o2c_hypothesis_matrix(
        matrix_csv_path=matrix_path,
        o2c_catalog_path=catalog,
    )
    assert payload["status"] == "ERROR"
    assert any("fraud_type no coincide con catálogo" in str(err) for err in payload["errors"])
    assert any("process_step no coincide con catálogo" in str(err) for err in payload["errors"])
