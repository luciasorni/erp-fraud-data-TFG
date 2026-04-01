from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.erp_fraud.graph import run_graph_full


def test_rf15c_13_multiagent_integration_with_llm_kb_duckdb_stubs(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
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
        output = kwargs["generate_fn"](
            kwargs["prompt_text"],
            dict(kwargs["input_payload"]),
            [],
            1,
        )
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

    def _fake_alpha_loop_result_to_dict(result: Any) -> dict[str, Any]:
        return {
            "status": str(result.status),
            "iterations": int(result.iterations),
            "artifacts_dir": str(result.artifacts_dir),
        }

    def _fake_build_kb_index(**kwargs: Any) -> dict[str, Any]:
        manifest_path = Path(str(kwargs["output_manifest_path"]))
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0.0",
            "chunks_indexed": 2,
            "sources_used": [{"source_id": "acfe_pdf"}],
            "sources_skipped": [],
            "persist_dir": str(tmp_path / "kb" / "chroma"),
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    class _FakeKBSearchTool:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def search(
            self,
            *,
            query: str,
            top_k: int = 5,
            filters: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            _ = filters
            return {
                "query": query,
                "count": min(top_k, 2),
                "hits": [
                    {
                        "chunk_id": "acfe-chunk-1",
                        "score": 0.9,
                        "metadata": {
                            "source_path": "docs/external/data_analytics_tests.pdf",
                            "source_id": "acfe_pdf",
                        },
                    },
                    {
                        "chunk_id": "acfe-chunk-2",
                        "score": 0.7,
                        "metadata": {
                            "source_path": "docs/external/data_analytics_tests.pdf",
                            "source_id": "acfe_pdf",
                        },
                    },
                ][:top_k],
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
                    "finding_count": 1,
                    "duration_ms": 12,
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
    monkeypatch.setattr(nodes, "alpha_loop_result_to_dict", _fake_alpha_loop_result_to_dict)
    monkeypatch.setattr(nodes, "build_kb_index", _fake_build_kb_index)
    monkeypatch.setattr(nodes, "KBSearchTool", _FakeKBSearchTool)
    monkeypatch.setattr(nodes, "TestRunner", _FakeRunner)

    out = run_graph_full(
        run_id="rf15c-13-integration",
        dataset_hash="hash-rf15c-13",
        input_zip="fixture.zip",
        run_metadata_overrides={
            "schema_summary_path": str(schema_summary_path),
            "catalog_path": "tests/catalog",
            "kb_index_enabled": True,
            "kb_search_enabled": True,
            "persist_base_dir": str(tmp_path / "run_results"),
            "test_planner_top_n": 1,
            "scoring_top_k": 10,
            "executor_timeout_ms": 2000,
        },
    )

    assert out.run_metadata["graph_status"] == "OK"
    assert out.run_metadata["node_status"]["ingest"] == "OK"
    assert out.run_metadata["node_status"]["kb_index"] == "OK"
    assert out.run_metadata["node_status"]["hypothesis_planner"] == "OK"
    assert out.run_metadata["node_status"]["test_planner"] == "OK"
    assert out.run_metadata["node_status"]["executor"] == "OK"
    assert out.run_metadata["node_status"]["explainer"] == "OK"
    assert out.run_metadata["node_status"]["scoring"] == "OK"
    assert out.run_metadata["node_status"]["persist"] == "OK"

    assert len(out.hypotheses) >= 1
    assert len(out.selected_tests) >= 1
    assert len(out.findings) == 1
    assert len(out.explanations) == 1
    assert len(out.scores) == 1
    assert len(out.fraud_type_predicho) == 1
    assert len(out.test_runs) == 1

    graph_dir = Path(out.run_metadata["persist_graph_dir"])
    assert (graph_dir / "hypotheses.json").exists()
    assert (graph_dir / "selected_tests.json").exists()
    assert (graph_dir / "explanations.json").exists()
    assert (graph_dir / "explanations.md").exists()
    assert (graph_dir / "score.json").exists()
    assert (graph_dir / "manifest.json").exists()
