from __future__ import annotations

import duckdb

from src.erp_fraud.catalog import TestRunner


def test_rf13_p2_unusual_posting_times_and_large_even_entries_execute(tmp_path) -> None:
    db_path = tmp_path / "rf13_p2_extra.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE fraud_1 (
              Kreditor VARCHAR,
              Belegnummer VARCHAR,
              Position VARCHAR,
              Betrag DOUBLE,
              Erfassungsuhrzeit VARCHAR,
              Transaktionsart VARCHAR,
              Sachkonto VARCHAR,
              "Soll/Haben-Kennz_" VARCHAR
            )
            """
        )
        conn.executemany(
            "INSERT INTO fraud_1 VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("V01", "5000000010", "10", 12000.0, "23:55:00", "N", "400000", "H"),
                ("V01", "5000000011", "10", 12500.0, "10:15:00", "N", "400000", "H"),
                ("V02", "5000000012", "20", 20000.0, "04:20:00", "N", "410000", "S"),
                ("V02", "5000000013", "20", 19999.0, "21:59:00", "N", "410000", "S"),
            ],
        )

        runner = TestRunner(db_path=db_path, schema_name="main", table_name="fraud_1")
        results = runner.run_all(
            selected_tests=[
                "TST-UNUSUAL-POSTING-TIMES",
                "TST-LARGE-EVEN-DOLLAR-ENTRIES",
            ],
            catalog_path="tests/catalog",
            validate_schema=True,
        )
    finally:
        conn.close()

    by_id = {str(row.get("test_id", "")): row for row in results if isinstance(row, dict)}
    assert by_id["TST-UNUSUAL-POSTING-TIMES"]["status"] == "OK"
    assert int(by_id["TST-UNUSUAL-POSTING-TIMES"]["finding_count"]) >= 2

    assert by_id["TST-LARGE-EVEN-DOLLAR-ENTRIES"]["status"] == "OK"
    assert int(by_id["TST-LARGE-EVEN-DOLLAR-ENTRIES"]["finding_count"]) >= 2
