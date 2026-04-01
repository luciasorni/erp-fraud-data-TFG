from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.erp_fraud.graph import run_graph_full


def test_rf15c_end_to_end_contract_outputs_are_consistent(monkeypatch: Any, tmp_path: Path) -> None:
    import src.erp_fraud.graph.nodes as nodes

    schema_summary_path = tmp_path / "schema_summary.json"
    schema_summary_path.write_text(
        json.dumps(
            {
                "schema_name": "main",
                "table_count": 1,
                "tables": [
                    {
                        "table_name": "fraud_1",
                        "columns": [
                            {"name": "Kreditor"},
                            {"name": "Belegnummer"},
                            {"name": "Position"},
                            {"name": "Betrag"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def _fake_alpha_loop(**kwargs: Any) -> Any:
        output = kwargs["generate_fn"](kwargs["prompt_text"], dict(kwargs["input_payload"]), [], 1)
        for validator in kwargs["validators"].values():
            result = validator(output, dict(kwargs["input_payload"]))
            assert bool(result.get("passed", False)), result
        return SimpleNamespace(
            status="OK",
            run_id=str(kwargs["run_id"]),
            node_id=str(kwargs["node_id"]),
            iterations=1,
            final_output=output,
            last_validation={"validation_passed": True, "checks": []},
            artifacts_dir=f"run_results/{kwargs['run_id']}/alphacodium/{kwargs['node_id']}",
        )

    class _FakeKBSearchTool:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def search(self, *, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> dict[str, Any]:
            _ = query, filters
            return {
                "count": min(1, top_k),
                "hits": [
                    {
                        "chunk_id": "acfe-contract-1",
                        "score": 0.8,
                        "metadata": {"source_path": "docs/external/data_analytics_tests.pdf", "source_id": "acfe"},
                    }
                ][:top_k],
            }

    def _fake_build_kb_index(**kwargs: Any) -> dict[str, Any]:
        return {
            "version": "1.0.0",
            "chunks_indexed": 1,
            "sources_used": [{"source_id": "acfe"}],
            "sources_skipped": [],
            "persist_dir": str(tmp_path / "kb" / "chroma"),
            "output_manifest_path": str(kwargs.get("output_manifest_path", "")),
        }

    class _FakeRunner:
        def __init__(self, *, db_path: str, schema_name: str, table_name: str) -> None:
            _ = db_path, schema_name, table_name

        def run_all(
            self,
            selected_tests: list[str],
            *,
            catalog_path: str,
            validate_schema: bool,
            timeout_ms: int | None,
            run_id: str | None,
            log_path: Path | None,
        ) -> list[dict[str, Any]]:
            _ = selected_tests, catalog_path, validate_schema, timeout_ms, run_id, log_path
            return [
                {
                    "result_schema_version": "1.0.0",
                    "generated_at_utc": "2026-01-01T00:00:00+00:00",
                    "test_id": "TST-DUPLICATE-POSTINGS",
                    "test_version": "1.0.0",
                    "fraud_type": "duplicate_payment",
                    "status": "OK",
                    "finding_count": 2,
                    "duration_ms": 10,
                    "columns": ["kreditor", "belegnummer", "duplicate_count"],
                    "rows": [
                        {
                            "entity_key": "kreditor=V1|belegnummer=D1",
                            "keys": {"kreditor": "V1", "belegnummer": "D1"},
                            "evidence_columns": ["kreditor", "belegnummer", "duplicate_count"],
                            "metrics": {"duplicate_count": 2},
                        }
                    ],
                    "metadata": {"implementation_type": "sql"},
                }
            ]

    monkeypatch.setattr(nodes, "alpha_loop", _fake_alpha_loop)
    monkeypatch.setattr(nodes, "KBSearchTool", _FakeKBSearchTool)
    monkeypatch.setattr(nodes, "build_kb_index", _fake_build_kb_index)
    monkeypatch.setattr(nodes, "TestRunner", _FakeRunner)
    monkeypatch.setattr(
        nodes,
        "alpha_loop_result_to_dict",
        lambda result: {"status": result.status, "iterations": result.iterations},
    )

    out = run_graph_full(
        run_id="rf15c-16-contract",
        dataset_hash="hash-rf15c-16",
        input_zip="fixture.zip",
        run_metadata_overrides={
            "schema_summary_path": str(schema_summary_path),
            "catalog_path": "tests/catalog",
            "kb_index_enabled": True,
            "kb_search_enabled": True,
            "persist_base_dir": str(tmp_path / "run_results"),
            "test_planner_top_n": 1,
            "scoring_top_k": 10,
        },
    )

    assert out.run_metadata["graph_status"] == "OK"
    assert out.selected_tests and out.recomendaciones
    assert out.findings and out.test_runs
    assert out.explanations and out.scores
    assert out.fraud_type_predicho and out.ranking

    score_payload = out.scores[0]
    probs = score_payload.get("fraud_type_probs", [])
    assert isinstance(probs, list) and probs
    prob_sum = sum(float(row.get("probability", 0.0) or 0.0) for row in probs if isinstance(row, dict))
    assert 0.999 <= prob_sum <= 1.001
