from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from src.erp_fraud.graph import run_graph_full


def test_rf14_graph_full_integration_with_deterministic_kb_stub(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import src.erp_fraud.graph.nodes as nodes

    def _fake_build_kb_index(**kwargs: Any) -> dict[str, Any]:
        manifest_path = Path(str(kwargs["output_manifest_path"]))
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0.0",
            "chunks_indexed": 1,
            "sources_used": [{"source_id": "stub_doc"}],
            "sources_skipped": [],
            "persist_dir": str(tmp_path / "kb" / "chroma"),
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    monkeypatch.setattr(nodes, "build_kb_index", _fake_build_kb_index)

    db_path = tmp_path / "rf14_13.duckdb"
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
        # Caso que activa TST-SPLIT-PAYMENTS-NEAR-LIMIT: dos líneas <1000 y suma >=1000.
        conn.executemany(
            "INSERT INTO fraud_1 VALUES (?, ?, ?, ?)",
            [
                ("V1", "D1", "10", 600.0),
                ("V1", "D1", "20", 500.0),
                ("V2", "D2", "10", 200.0),
            ],
        )
    finally:
        conn.close()

    out = run_graph_full(
        run_id="rf14-13-integration",
        dataset_hash="hash-rf14-13",
        input_zip="fixture.zip",
        run_metadata_overrides={
            "db_path": str(db_path),
            "schema_name": "main",
            "table_name": "fraud_1",
            "catalog_path": "tests/catalog",
            "kb_index_enabled": True,
            "kb_search_enabled": False,
            "persist_base_dir": str(tmp_path / "run_results"),
            "executor_timeout_ms": 2000,
            "test_planner_top_n": 1,
            "scoring_top_k": 10,
        },
    )

    assert out.run_metadata["graph_status"] == "OK"
    assert out.run_metadata["node_status"]["ingest"] == "OK"
    assert out.run_metadata["node_status"]["kb_index"] == "OK"
    assert out.run_metadata["node_status"]["executor"] == "OK"
    assert out.run_metadata["node_status"]["persist"] == "OK"

    assert len(out.hypotheses) >= 1
    assert len(out.selected_tests) >= 1
    assert len(out.findings) >= 1
    assert len(out.explanations) >= 1
    assert len(out.scores) == 1

    graph_dir = Path(out.run_metadata["persist_graph_dir"])
    assert (graph_dir / "manifest.json").exists()
    assert (graph_dir / "findings.json").exists()
    assert (graph_dir / "scores.json").exists()

