from __future__ import annotations

import json
from pathlib import Path

import duckdb

from src.erp_fraud.graph import run_graph_full


def test_rf16_second_level_agent_runs_after_persist(tmp_path: Path) -> None:
    db_path = tmp_path / "rf16_node.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE fraud_1 (
                Kreditor VARCHAR,
                Belegnummer VARCHAR,
                Position VARCHAR,
                Betrag DOUBLE
            )
            """
        )
        conn.executemany(
            "INSERT INTO fraud_1 VALUES (?, ?, ?, ?)",
            [
                ("V1", "D1", "10", 8039295.0),
                ("V1", "D1", "20", 4984.0),
                ("V2", "D2", "10", 120.0),
            ],
        )
    finally:
        conn.close()

    out = run_graph_full(
        run_id="rf16-node-it",
        dataset_hash="hash-rf16-node",
        input_zip="fixture.zip",
        run_metadata_overrides={
            "db_path": str(db_path),
            "schema_name": "main",
            "table_name": "fraud_1",
            "catalog_path": "tests/catalog",
            "persist_base_dir": str(tmp_path / "run_results"),
            "llm_mode": "stub",
            "kb_index_enabled": False,
            "kb_search_enabled": False,
            "rf16_include_current_run": True,
            "rf16_auto_latest_p2p_o2c": False,
            "rf16_compare_run_ids": [],
        },
    )

    node_status = out.run_metadata.get("node_status", {})
    assert isinstance(node_status, dict)
    assert node_status.get("persist") == "OK"
    assert node_status.get("second_level_explainer") == "OK"

    graph_dir = Path(str(out.run_metadata.get("persist_graph_dir", "")).strip())
    assert (graph_dir / "second_level_analysis.json").exists()
    assert (graph_dir / "second_level_analysis.md").exists()

    payload = json.loads((graph_dir / "second_level_analysis.json").read_text(encoding="utf-8"))
    assert payload.get("rf_task") == "RF16"
    assert isinstance(payload.get("deterministic_comparison"), dict)
    assert isinstance(payload.get("llm_insights"), dict)
