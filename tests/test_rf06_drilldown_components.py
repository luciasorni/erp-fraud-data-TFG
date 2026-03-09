from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from src.erp_fraud.catalog import (
    DRILLDOWN_MIN_KEYS_BY_TEST_ID,
    DRILLDOWN_QUERY_ID_BY_TEST_ID,
    get_minimum_keys_for_test_id,
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

