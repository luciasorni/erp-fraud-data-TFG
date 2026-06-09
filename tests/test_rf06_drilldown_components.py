from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from src.erp_fraud.catalog import (
    DRILLDOWN_MIN_KEYS_BY_TEST_ID,
    DRILLDOWN_QUERY_ID_BY_TEST_ID,
    build_drilldown_template_ref,
    get_minimum_keys_for_test_id,
    get_missing_or_empty_minimum_keys_for_test_id,
    normalize_drilldown_keys,
    validate_minimum_keys_for_test_id,
)
from src.erp_fraud.catalog.drilldown import drilldown
from src.erp_fraud.cli.main import main as cli_main


def _build_test_db(path: Path) -> Path:
    conn = duckdb.connect(str(path))
    conn.execute(
        """
        CREATE TABLE fraud_1 (
            Kreditor VARCHAR,
            Belegnummer VARCHAR,
            Position VARCHAR,
            Betrag DOUBLE,
            Transaktionsart VARCHAR
        )
        """
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?)",
        [
            ("V1", "D1", "10", 100.0, "N"),
            ("V1", "D1", "10", 100.0, "N"),
            ("V1", "D9", "90", 100.0, "X"),
            ("V2", "D2", "20", 200.0, "N"),
        ],
    )
    conn.close()
    return path


def test_minimum_keys_contract_available() -> None:
    assert "TST-DUPLICATE-POSTINGS" in DRILLDOWN_MIN_KEYS_BY_TEST_ID
    assert "TST-UNUSUAL-AMOUNT-BY-VENDOR" in DRILLDOWN_MIN_KEYS_BY_TEST_ID
    assert "TST-DUPLICATE-POSTINGS" in DRILLDOWN_QUERY_ID_BY_TEST_ID

    keys = get_minimum_keys_for_test_id("TST-DUPLICATE-POSTINGS")
    assert keys == ("kreditor", "belegnummer", "position", "betrag")


def test_validate_minimum_keys_rejects_missing() -> None:
    with pytest.raises(ValueError, match="Faltan"):
        validate_minimum_keys_for_test_id(
            "TST-DUPLICATE-POSTINGS",
            {"kreditor": "V1", "belegnummer": "D1"},
        )


def test_normalize_and_validate_keys_rejects_empty_values() -> None:
    normalized = normalize_drilldown_keys(
        {"company_code": "1000", "receivable_document_id": "  ", "fiscal_year": 2025, "kreditor": "None"}
    )
    assert normalized == {"company_code": "1000", "fiscal_year": "2025"}
    missing = get_missing_or_empty_minimum_keys_for_test_id(
        "TST-O2C-CLEARING-ANOMALY",
        {"company_code": "1000", "receivable_document_id": "  ", "fiscal_year": 2025},
    )
    assert missing == ["receivable_document_id"]


def test_drilldown_template_omits_null_like_params() -> None:
    ref = build_drilldown_template_ref(
        test_id="TST-DUPLICATE-MATERIAL-ITEMS",
        keys={
            "kreditor": "None",
            "belegnummer": "4900001152",
            "position": "1",
            "material": "AA-F03",
            "empty": None,
        },
    )
    assert ref["params"] == {
        "belegnummer": "4900001152",
        "position": "1",
        "material": "AA-F03",
    }


def test_drilldown_rejects_invalid_order_and_filter(tmp_path: Path) -> None:
    db_path = _build_test_db(tmp_path / "rf06_components.duckdb")
    keys = {
        "kreditor": "V1",
        "belegnummer": "D1",
        "position": "10",
        "betrag": "100.0",
    }

    with pytest.raises(ValueError, match="order_direction"):
        drilldown(
            test_id="TST-DUPLICATE-POSTINGS",
            keys=keys,
            db_path=db_path,
            order_direction="INVALID",
        )

    with pytest.raises(ValueError, match="extra_filters no permitidos"):
        drilldown(
            test_id="TST-DUPLICATE-POSTINGS",
            keys=keys,
            db_path=db_path,
            extra_filters={"NoPermitido": "x"},
        )


def test_drilldown_limit_and_allowed_filter(tmp_path: Path) -> None:
    db_path = _build_test_db(tmp_path / "rf06_limit_filter.duckdb")
    keys = {
        "kreditor": "V1",
        "belegnummer": "D1",
        "position": "10",
        "betrag": "100.0",
    }

    rows = drilldown(
        test_id="TST-DUPLICATE-POSTINGS",
        keys=keys,
        db_path=db_path,
        limit_rows=1,
        order_direction="ASC",
        extra_filters={"Transaktionsart": "N"},
    )
    assert len(rows) == 1
    assert rows[0]["Kreditor"] == "V1"
    assert rows[0]["Transaktionsart"] == "N"


def test_p2p_drilldown_normalizes_numeric_like_and_spaced_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "rf06_p2p_normalized_keys.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE fraud_1 (
            Kreditor VARCHAR,
            Belegnummer VARCHAR,
            Position VARCHAR,
            Betrag DOUBLE,
            Material VARCHAR,
            Transaktionsart VARCHAR
        )
        """
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("123.0", "4500001.0", "10.0", 100.0, " MAT-01 ", "N"),
            ("123.0", "4500001.0", "20.0", 100.0, " MAT-01 ", "N"),
        ],
    )
    conn.close()

    rows_amount = drilldown(
        test_id="TST-UNUSUAL-AMOUNT-BY-VENDOR",
        keys={"kreditor": "123", "betrag": "100.0"},
        db_path=db_path,
    )
    rows_material = drilldown(
        test_id="TST-DUPLICATE-MATERIAL-ITEMS",
        keys={
            "kreditor": "123",
            "belegnummer": "4500001",
            "position": "10",
            "material": "MAT-01",
        },
        db_path=db_path,
    )
    assert len(rows_amount) == 2
    assert len(rows_material) == 1
    assert rows_material[0]["Position"] == "10.0"


def test_duplicate_material_drilldown_allows_missing_kreditor_for_null_source(tmp_path: Path) -> None:
    db_path = tmp_path / "rf06_duplicate_material_null_kreditor.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE fraud_1 (
            Kreditor VARCHAR,
            Belegnummer VARCHAR,
            Position VARCHAR,
            Betrag DOUBLE,
            Material VARCHAR,
            Transaktionsart VARCHAR
        )
        """
    )
    conn.executemany(
        "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?, ?)",
        [
            (None, "4900001152", "1", 100.0, "AA-F03", "N"),
            (None, "4900001152", "1", 101.0, "AA-F03", "N"),
            ("V1", "4900001152", "1", 102.0, "AA-F03", "N"),
        ],
    )
    conn.close()

    rows = drilldown(
        test_id="TST-DUPLICATE-MATERIAL-ITEMS",
        keys={"belegnummer": "4900001152", "position": "1", "material": "AA-F03"},
        db_path=db_path,
    )

    assert len(rows) == 3
    assert {row["Material"] for row in rows} == {"AA-F03"}


def test_o2c_drilldown_cases_execute_with_minimum_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "rf06_o2c.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE SCHEMA o2c")
    conn.execute(
        """
        CREATE TABLE o2c.o2c_delivery (
            delivery_id VARCHAR,
            delivery_item_id VARCHAR,
            delivered_quantity DOUBLE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE o2c.o2c_collection (
            company_code VARCHAR,
            receivable_document_id VARCHAR,
            fiscal_year VARCHAR,
            amount_local_currency DOUBLE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE o2c.o2c_order (
            sales_order_id VARCHAR,
            sales_order_item_id VARCHAR,
            customer_id VARCHAR
        )
        """
    )
    conn.executemany("INSERT INTO o2c.o2c_delivery VALUES (?, ?, ?)", [("D1", "10", 5.0)])
    conn.executemany("INSERT INTO o2c.o2c_collection VALUES (?, ?, ?, ?)", [("1000", "RV1", "2025", 100.0)])
    conn.executemany("INSERT INTO o2c.o2c_order VALUES (?, ?, ?)", [("SO1", "20", "C1")])
    conn.close()

    delivery = drilldown(
        test_id="TST-O2C-DELIVERY-QUANTITY-MISMATCH",
        keys={"delivery_id": "D1", "delivery_item_id": "10"},
        db_path=db_path,
    )
    clearing = drilldown(
        test_id="TST-O2C-CLEARING-ANOMALY",
        keys={"company_code": "1000", "receivable_document_id": "RV1", "fiscal_year": "2025"},
        db_path=db_path,
    )
    discount = drilldown(
        test_id="TST-O2C-DISCOUNT-POLICY-BREACH",
        keys={"sales_order_id": "SO1", "sales_order_item_id": "20"},
        db_path=db_path,
    )
    assert delivery[0]["delivery_id"] == "D1"
    assert clearing[0]["receivable_document_id"] == "RV1"
    assert discount[0]["sales_order_id"] == "SO1"


def test_cli_drilldown_saves_default_output(tmp_path: Path) -> None:
    db_path = _build_test_db(tmp_path / "rf06_cli.duckdb")
    run_id = "rf06-08-cli-check"
    rc = cli_main(
        [
            "drilldown",
            "--run-id",
            run_id,
            "--test-id",
            "TST-DUPLICATE-POSTINGS",
            "--entity-key",
            "belegnummer=D1|betrag=100.0|kreditor=V1|position=10",
            "--db-path",
            str(db_path),
            "--save-default",
        ]
    )
    assert rc == 0

    out = Path("run_results") / run_id / "drilldown_TST-DUPLICATE-POSTINGS.json"
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["test_id"] == "TST-DUPLICATE-POSTINGS"
    assert payload["row_count"] >= 1
