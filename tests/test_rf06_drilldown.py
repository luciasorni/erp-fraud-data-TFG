from __future__ import annotations

from pathlib import Path

import duckdb

from src.erp_fraud.catalog import drilldown
from src.erp_fraud.catalog.test_runner import TestRunner as CatalogRunner


def test_drilldown_returns_rows_for_known_duplicate_finding(tmp_path: Path) -> None:
    db_path = tmp_path / "rf06_drilldown.duckdb"
    conn = duckdb.connect(str(db_path))
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
            ("V2", "D2", "20", 200.0, "N"),
        ],
    )
    conn.close()

    runner = CatalogRunner(db_path=db_path, schema_name="main", table_name="fraud_1")
    results = runner.run_all(
        ["TST-DUPLICATE-POSTINGS"],
        catalog_path="tests/catalog",
        validate_schema=True,
    )
    assert len(results) == 1
    assert results[0]["status"] == "OK"
    assert results[0]["finding_count"] >= 1

    finding = results[0]["rows"][0]
    keys = {k: str(v) for k, v in finding["keys"].items()}

    rows = drilldown(
        test_id="TST-DUPLICATE-POSTINGS",
        keys=keys,
        db_path=db_path,
        schema_name="main",
        table_name="fraud_1",
        limit_rows=200,
        order_direction="ASC",
    )

    assert len(rows) >= 2
    assert all(str(row["Kreditor"]) == "V1" for row in rows)
    assert all(str(row["Belegnummer"]) == "D1" for row in rows)
