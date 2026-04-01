from __future__ import annotations

import json
from pathlib import Path

import duckdb

from src.erp_fraud.graph import create_initial_graph_state, ingest_node


def test_rf14_ingest_node_loads_schema_from_duckdb(tmp_path: Path) -> None:
    db_path = tmp_path / "rf14_ingest.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE fraud_1 (Kreditor VARCHAR, Betrag DOUBLE)")
    finally:
        conn.close()

    state = create_initial_graph_state(run_id="rf14-03-duckdb")
    state.run_metadata["db_path"] = str(db_path)
    state.run_metadata["schema_name"] = "main"

    out = ingest_node(state)

    assert out.schema["schema_name"] == "main"
    assert out.schema["table_count"] >= 1
    assert out.run_metadata["ingest_source"] == "duckdb"
    assert out.run_metadata["ingest_table_count"] >= 1


def test_rf14_ingest_node_loads_schema_from_json_path(tmp_path: Path) -> None:
    schema_summary_path = tmp_path / "schema_summary.json"
    schema_summary_path.write_text(
        json.dumps(
            {
                "schema_name": "main",
                "table_count": 1,
                "tables": [
                    {
                        "table_schema": "main",
                        "table_name": "fraud_1",
                        "columns": [{"name": "Kreditor", "type": "VARCHAR"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    state = create_initial_graph_state(run_id="rf14-03-json")
    state.run_metadata["schema_summary_path"] = str(schema_summary_path)

    out = ingest_node(state)

    assert out.schema["table_count"] == 1
    assert out.run_metadata["ingest_source"] == "schema_summary_json"
    assert out.run_metadata["ingest_schema_summary_path"] == str(schema_summary_path)

