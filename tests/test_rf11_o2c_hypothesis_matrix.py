from __future__ import annotations

import csv
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
