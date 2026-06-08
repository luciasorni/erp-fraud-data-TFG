from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.api.schemas.datasets import DatasetDetailResponse
from app.api.schemas.results import GraphResultsResponse
from app.api.schemas.runs import RunCreateRequest
from app.api.services.aws_service import AWSAPISettings
from app.api.services import drilldown_service
from app.api.services.results_service import load_graph_results, load_report
from app.api.services.runs_service import create_run, list_runs


def _settings() -> AWSAPISettings:
    return AWSAPISettings(
        aws_region="eu-west-1",
        aws_profile=None,
        s3_input_uri="s3://bucket/inputs/",
        s3_output_uri="s3://bucket/runs/",
        ecs_cluster="cluster",
        ecs_task_definition="taskdef",
        subnet_ids=("subnet-a", "subnet-b"),
        security_group_ids=("sg-a",),
    )


def test_rf20_runs_service_both_orchestrates_two_runs(monkeypatch) -> None:
    submitted = []
    recorded_payloads = []

    monkeypatch.setattr(
        "app.api.services.runs_service.get_dataset",
        lambda **kwargs: DatasetDetailResponse(
            dataset_id="ds-001",
            file_name="erp_fraud_data.zip",
            scopes=["p2p", "o2c"],
            validation_status="VALID",
            dataset_hash="abc",
            uploaded_at_utc=datetime.now(timezone.utc).replace(microsecond=0),
            files_detected=["README.txt"],
            expected_files=["README.txt"],
            s3_keys={
                "p2p": "inputs/datasets/p2p/ds-001/erp_fraud_data.zip",
                "o2c": "inputs/datasets/o2c/ds-001/erp_fraud_data.zip",
            },
            metadata_key="inputs/datasets/registry/ds-001.json",
            size_bytes=100,
        ),
    )
    monkeypatch.setattr("app.api.services.runs_service.ensure_dataset_supports_scope", lambda **kwargs: None)

    def _fake_submit_graph_run_task(**kwargs):
        submitted.append(kwargs)
        return f"task::{kwargs['process_scope']}"

    monkeypatch.setattr("app.api.services.runs_service.submit_graph_run_task", _fake_submit_graph_run_task)
    monkeypatch.setattr(
        "app.api.services.runs_service.write_run_submission_record",
        lambda **kwargs: recorded_payloads.append(kwargs["payload"]) or "ok",
    )

    out = create_run(
        payload=RunCreateRequest(
            dataset_id="ds-001",
            scope="both",
            pipeline_mode="graph",
            llm_mode="real",
            kb_index_enabled=True,
        ),
        settings=_settings(),
        s3_client=object(),
        ecs_client=object(),
    )
    assert out.composite_run is True
    assert out.run_ids is not None
    assert out.run_ids.p2p is not None
    assert out.run_ids.o2c is not None
    assert {item["process_scope"] for item in submitted} == {"p2p", "o2c"}
    assert {item["process_family"] for item in submitted} == {"p2p", "o2c"}
    assert len(recorded_payloads) == 2
    assert all(payload["composite_run"] is True for payload in recorded_payloads)
    assert all(payload["composite_group_id"] for payload in recorded_payloads)
    assert all(isinstance(payload["peer_run_ids"], list) and len(payload["peer_run_ids"]) == 1 for payload in recorded_payloads)


def test_rf20_runs_service_list_runs_is_lightweight_and_limited(monkeypatch) -> None:
    prefixes = [
        "runs/api-p2p-graph-20260415-120000/",
        "runs/api-p2p-graph-20260416-110000/",
        "runs/api-o2c-graph-20260416-113000/",
    ]
    api_requests = {
        "api-o2c-graph-20260416-113000": {
            "dataset_id": "ds-o2c",
            "scope": "o2c",
            "pipeline_mode": "graph",
            "llm_mode": "real",
            "kb_index_enabled": False,
            "task_arn": "task-o2c",
            "submitted_at_utc": "2026-04-16T11:30:00+00:00",
        },
        "api-p2p-graph-20260416-110000": {
            "dataset_id": "ds-p2p",
            "scope": "p2p",
            "pipeline_mode": "graph",
            "llm_mode": "real",
            "kb_index_enabled": True,
            "task_arn": "task-p2p",
            "submitted_at_utc": "2026-04-16T11:00:00+00:00",
        },
    }
    graph_states = {
        "api-o2c-graph-20260416-113000": {
            "run_metadata": {
                "graph_status": "OK",
                "kb_index_status": "SKIPPED_NO_REBUILD",
                "process_scope": "o2c",
                "process_family": "o2c",
                "updated_at_utc": "2026-04-16T11:35:00+00:00",
            }
        },
        "api-p2p-graph-20260416-110000": {
            "run_metadata": {
                "graph_status": "ABORTED",
                "kb_index_status": "OK",
                "process_scope": "p2p",
                "process_family": "p2p",
                "updated_at_utc": "2026-04-16T11:05:00+00:00",
            }
        },
    }

    monkeypatch.setattr("app.api.services.runs_service.list_s3_common_prefixes", lambda **kwargs: prefixes)
    monkeypatch.setattr("app.api.services.runs_service.get_run", lambda **kwargs: (_ for _ in ()).throw(AssertionError("get_run should not be used")))
    monkeypatch.setattr(
        "app.api.services.runs_service._load_run_api_request",
        lambda *, run_id, settings, s3_client: api_requests.get(run_id),
    )
    monkeypatch.setattr(
        "app.api.services.runs_service._load_run_metadata",
        lambda *, run_id, settings, s3_client: None,
    )
    monkeypatch.setattr(
        "app.api.services.runs_service._load_graph_state",
        lambda *, run_id, settings, s3_client: graph_states.get(run_id),
    )

    out = list_runs(settings=_settings(), s3_client=object(), limit=2)
    assert [item.run_id for item in out] == [
        "api-o2c-graph-20260416-113000",
        "api-p2p-graph-20260416-110000",
    ]
    assert out[0].status == "COMPLETED"
    assert out[1].status == "FAILED"


def test_rf20_runs_service_list_runs_uses_short_cache(monkeypatch) -> None:
    call_count = {"prefixes": 0}

    def _fake_prefixes(**kwargs):
        call_count["prefixes"] += 1
        return ["runs/api-p2p-graph-20260416-110000/"]

    monkeypatch.setattr("app.api.services.runs_service._RUNS_LIST_CACHE", {})
    monkeypatch.setattr("app.api.services.runs_service.list_s3_common_prefixes", _fake_prefixes)
    monkeypatch.setattr(
        "app.api.services.runs_service._load_run_api_request",
        lambda *, run_id, settings, s3_client: {
            "dataset_id": "ds-001",
            "scope": "p2p",
            "pipeline_mode": "graph",
            "llm_mode": "real",
            "kb_index_enabled": False,
            "task_arn": "task-001",
            "submitted_at_utc": "2026-04-16T11:00:00+00:00",
        },
    )
    monkeypatch.setattr("app.api.services.runs_service._load_run_metadata", lambda **kwargs: None)
    monkeypatch.setattr(
        "app.api.services.runs_service._load_graph_state",
        lambda **kwargs: {
            "run_metadata": {
                "graph_status": "OK",
                "kb_index_status": "SKIPPED_NO_REBUILD",
                "process_scope": "p2p",
                "updated_at_utc": "2026-04-16T11:05:00+00:00",
            }
        },
    )

    first = list_runs(settings=_settings(), s3_client=object(), limit=20)
    second = list_runs(settings=_settings(), s3_client=object(), limit=20)
    assert len(first) == 1
    assert len(second) == 1
    assert call_count["prefixes"] == 1


def test_rf20_results_service_load_graph_results_shapes_ui_payload(monkeypatch) -> None:
    artifacts = {
        "graph/graph_state.json": {
            "run_metadata": {
                "graph_status": "OK",
                "kb_index_status": "OK",
                "process_scope": "p2p",
            }
        },
        "graph/hypotheses.json": [
            {
                "hypothesis_id": "HYP-001",
                "title": "Amount anomaly",
                "fraud_type": "amount_anomaly",
                "description": "Check anomalous amounts",
                "candidate_test_ids": ["TST-UNUSUAL-AMOUNT-BY-VENDOR"],
                "process_step": "invoice_posting",
                "tool_context": {"kb_hits_count": 3},
            }
        ],
        "graph/selected_tests.json": [
            {
                "hypothesis_id": "HYP-001",
                "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                "match_reasons": ["fraud_type:amount_anomaly"],
                "score": 6,
                "source": "planner_allowlist_heuristic",
            }
        ],
        "graph/findings.json": [
            {
                "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                "fraud_type": "amount_anomaly",
                "status": "OK",
                "finding_count": 2,
                "columns": ["kreditor", "betrag"],
                "rows": [
                    {
                        "entity_key": "betrag=100|kreditor=V01",
                        "keys": {"betrag": "100", "kreditor": "V01"},
                        "drilldown_template": {"query_id": "drilldown_unusual_amount_by_vendor_v1"},
                    }
                ],
            }
        ],
        "graph/scores.json": [
            {
                "final_label": "amount_anomaly",
                "confidence": 0.8,
                "source": "scoring_node",
                "evidence_summary": "evidence",
                "fraud_type_distribution": {"amount_anomaly": 2},
                "ranking": [{"entity_key": "betrag=100|kreditor=V01"}],
                "summary": {"entities_scored": 1},
            }
        ],
        "graph/explanations.json": [
            {
                "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                "fraud_type": "amount_anomaly",
                "status": "OK",
                "summary": "Explains why it is suspicious",
                "cited_test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                "cited_keys": {"betrag": "100"},
                "referenced_columns": ["betrag"],
            }
        ],
        "graph/second_level_analysis.json": {
            "deterministic_comparison": {
                "comparison_sections": [
                    {
                        "title": "Comparación histórica intra-familia",
                        "subtitle": "1 run previo de P2P",
                        "summary": "El run actual se ha comparado con un run previo de la misma familia.",
                        "section": "historical",
                        "status": "comparison",
                        "evidence": ["Runs históricos: run-prev-001."],
                    }
                ],
                "summary": {
                    "common_selected_tests": ["TST-UNUSUAL-AMOUNT-BY-VENDOR"],
                    "common_fraud_types_with_findings": ["amount_anomaly"],
                }
            },
            "llm_insights": {
                "executive_summary": {
                    "overall_assessment": "The case deviates from the expected vendor pattern.",
                    "risk_posture": "High",
                    "key_observations": ["The same anomaly appears consistently in the selected evidence."],
                },
                "cross_process_conclusions": [
                    {
                        "title": "Desviación relevante",
                        "summary": "The same anomaly appears consistently in the selected evidence.",
                        "section": "historical",
                        "status": "comparison",
                    }
                ],
                "audit_procedures": [{"procedure": "Validate invoice lineage for vendor V01.", "why": "Trace end-to-end lineage."}],
                "recommended_tests": [{"test_id": "TST-PEER-AMOUNT-DISPERSION", "rationale": "Compare V01 against peer vendors."}],
                "next_actions": [{"action": "Open a targeted manual review for vendor V01.", "why": "Prioritised signal."}],
                "normalized": {
                    "executive_summary": {
                        "overall_assessment": "The case deviates from the expected vendor pattern.",
                        "risk_posture": "High",
                        "key_observations": ["The same anomaly appears consistently in the selected evidence."],
                    },
                    "comparison_items": [
                        {
                            "title": "Desviación relevante",
                            "summary": "The same anomaly appears consistently in the selected evidence.",
                            "section": "historical",
                            "status": "comparison",
                        }
                    ],
                    "recommendation_items": [
                        {
                            "title": "Open a targeted manual review for vendor V01.",
                            "summary": "Prioritised signal.",
                            "status": "recommended_action",
                            "section": "recommendations",
                        },
                        {
                            "title": "TST-PEER-AMOUNT-DISPERSION",
                            "summary": "Compare V01 against peer vendors.",
                            "status": "recommended_test",
                            "section": "recommended_tests",
                        },
                        {
                            "title": "Validate invoice lineage for vendor V01.",
                            "summary": "Trace end-to-end lineage.",
                            "status": "audit_procedure",
                            "section": "audit_procedures",
                        },
                    ],
                },
            },
        },
        "api_request.json": {"dataset_id": "ds-001", "scope": "p2p", "peer_run_ids": []},
        "run_metadata.json": {"dataset_hash": "hash-001"},
        "report.json": {"summary": {"overall_status": "OK", "findings_total": 2}, "metadata": {"metadata_extra": {}}},
    }

    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    monkeypatch.setattr("app.api.services.results_service.list_s3_common_prefixes", lambda **kwargs: [])
    out = load_graph_results(run_id="run-001", status="COMPLETED", scope="p2p", settings=_settings(), s3_client=object())
    assert isinstance(out, GraphResultsResponse)
    assert out.counts.hypotheses == 1
    assert out.counts.selected_tests == 1
    assert out.counts.findings == 1
    assert out.counts.scores == 1
    assert out.counts.explanations == 1
    assert out.counts.second_level_analysis == 3
    assert out.executive_summary["overall_assessment"] == "The case deviates from the expected vendor pattern."
    assert out.hypotheses[0].title == "Amount anomaly"
    assert out.findings[0].attributes["sample_entity_key"] == "betrag=100|kreditor=V01"
    assert out.findings[0].attributes["process_step"] == "invoice_posting"
    assert out.selected_tests[0].attributes["hypothesis_id"] == "HYP-001"
    assert out.selected_tests[0].attributes["process_step"] == "invoice_posting"
    assert out.explanations[0].attributes["finding_count"] == 2
    recommended_test = next(item for item in out.second_level_analysis if item.status == "recommended_test")
    assert recommended_test.title == "TST-PEER-AMOUNT-DISPERSION"
    assert recommended_test.summary == "Compare V01 against peer vendors."
    assert out.second_level_analysis[0].title == "Open a targeted manual review for vendor V01."
    assert out.comparison_insights[0].title == "Lectura del run actual"
    assert any(item.attributes.get("section") == "historical" for item in out.comparison_insights)
    assert any(item.attributes.get("section") == "cross_process" for item in out.comparison_insights)
    assert out.scores[0].attributes["confidence"] == 0.8


def test_rf20_results_service_loads_legacy_second_level_raw_lists(monkeypatch) -> None:
    artifacts = {
        "graph/graph_state.json": {"run_metadata": {"graph_status": "OK", "process_scope": "p2p"}},
        "graph/hypotheses.json": [],
        "graph/selected_tests.json": [],
        "graph/findings.json": [],
        "graph/scores.json": [],
        "graph/explanations.json": [],
        "graph/second_level_analysis.json": {
            "llm_insights": {
                "executive_summary": "Legacy second-level output.",
                "audit_procedures": [
                    {
                        "procedure": "Reconciliar factura, pedido y pago para el proveedor V01.",
                        "why": "Confirma la trazabilidad documental.",
                        "priority": "high",
                    }
                ],
                "recommended_tests": [
                    {
                        "test_id": "TST-PEER-AMOUNT-DISPERSION",
                        "rationale": "Compara V01 con proveedores equivalentes.",
                        "priority": "medium",
                    }
                ],
                "next_actions": [
                    {
                        "action": "Abrir revisión manual para V01.",
                        "why": "La señal queda priorizada.",
                        "priority": "high",
                    }
                ],
            }
        },
        "api_request.json": {"dataset_id": "ds-001", "scope": "p2p", "peer_run_ids": []},
        "run_metadata.json": {"dataset_hash": "hash-001"},
        "report.json": {"summary": {"overall_status": "OK", "findings_total": 0}, "metadata": {"metadata_extra": {}}},
    }

    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    monkeypatch.setattr("app.api.services.results_service.list_s3_common_prefixes", lambda **kwargs: [])

    out = load_graph_results(run_id="run-legacy", status="COMPLETED", scope="p2p", settings=_settings(), s3_client=object())

    assert out.counts.second_level_analysis == 3
    by_status = {item.status: item for item in out.second_level_analysis}
    assert by_status["audit_procedure"].title == "Reconciliar factura, pedido y pago para el proveedor V01."
    assert by_status["audit_procedure"].summary == "Confirma la trazabilidad documental."
    assert by_status["audit_procedure"].attributes["priority"] == "high"
    assert by_status["recommended_test"].title == "TST-PEER-AMOUNT-DISPERSION"
    assert by_status["recommended_test"].summary == "Compara V01 con proveedores equivalentes."
    assert by_status["recommended_action"].title == "Abrir revisión manual para V01."
    assert by_status["recommended_action"].summary == "La señal queda priorizada."


def test_rf20_results_service_prefers_related_cross_process_comparison(monkeypatch) -> None:
    artifacts = {
        "graph/graph_state.json": {"run_metadata": {"graph_status": "OK", "kb_index_status": "OK", "process_scope": "p2p"}},
        "graph/hypotheses.json": [],
        "graph/selected_tests.json": [],
        "graph/findings.json": [],
        "graph/scores.json": [],
        "graph/explanations.json": [],
        "graph/second_level_analysis.json": {
            "deterministic_comparison": {"comparison_sections": []},
            "llm_insights": {
                "normalized": {
                    "comparison_items": [
                        {
                            "title": "Comparación cross-process",
                            "summary": "No hay runs de otra familia de proceso con contexto suficiente para evaluar concurrencia o divergencia cross-process.",
                            "section": "cross_process",
                            "status": "insufficient_context",
                        }
                    ]
                }
            },
        },
        "api_request.json": {"dataset_id": "ds-001", "scope": "p2p", "peer_run_ids": ["run-o2c"]},
        "run_metadata.json": {"dataset_hash": "hash-001"},
        "report.json": {"summary": {"overall_status": "OK", "findings_total": 0}, "metadata": {"metadata_extra": {}}},
    }
    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    monkeypatch.setattr(
        "app.api.services.results_service._build_related_comparison_payload",
        lambda **kwargs: {
            "comparison_sections": [
                {
                    "title": "Comparación cross-process",
                    "summary": "El run actual se ha contrastado con 1 run(s) de otra familia de proceso para identificar concurrencia o divergencia de señal.",
                    "section": "cross_process",
                    "status": "comparison",
                    "evidence": ["Runs cross-process: run-o2c."],
                }
            ]
        },
    )
    out = load_graph_results(run_id="run-p2p", status="COMPLETED", scope="p2p", settings=_settings(), s3_client=object())
    cross_process = next(item for item in out.comparison_insights if item.attributes.get("section") == "cross_process")
    assert cross_process.status == "comparison"
    assert "run(s) de otra familia" in (cross_process.summary or "")


def test_rf20_results_service_normalizes_drilldown_context_for_o2c_findings(monkeypatch) -> None:
    artifacts = {
        "graph/graph_state.json": {
            "run_metadata": {
                "graph_status": "OK",
                "kb_index_status": "OK",
                "process_scope": "o2c",
            }
        },
        "graph/hypotheses.json": [],
        "graph/selected_tests.json": [],
        "graph/findings.json": [
            {
                "test_id": "TST-O2C-DELIVERY-QUANTITY-MISMATCH",
                "fraud_type": "delivery_manipulation",
                "status": "OK",
                "finding_count": 1,
                "columns": ["delivery_id", "delivery_item_id", "delivered_quantity"],
                "rows": [
                    {
                        "entity_key": "delivery_id=D1|delivery_item_id=10",
                        "keys": {"delivery_id": "D1", "delivery_item_id": "10"},
                        "drilldown_template": {
                            "query_id": "drilldown_o2c_delivery_quantity_mismatch_v1",
                            "params": {"delivery_id": "D1", "delivery_item_id": "10"},
                        },
                    }
                ],
            }
        ],
        "graph/scores.json": [],
        "graph/explanations.json": [],
        "graph/second_level_analysis.json": {},
    }
    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    out = load_graph_results(run_id="run-o2c", status="COMPLETED", scope="o2c", settings=_settings(), s3_client=object())
    finding = out.findings[0]
    assert finding.attributes["drilldown_ready"] is True
    assert finding.attributes["sample_query_id"] == "drilldown_o2c_delivery_quantity_mismatch_v1"
    assert finding.attributes["rows"][0]["query_id"] == "drilldown_o2c_delivery_quantity_mismatch_v1"


def test_rf20_drilldown_service_rebuilds_o2c_cache_if_required_table_missing(tmp_path, monkeypatch) -> None:
    cache_root = tmp_path / "cache"
    db_dir = cache_root / "ds-001" / "o2c"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "erp.duckdb"
    db_path.write_text("stale-cache", encoding="utf-8")

    calls = {"ensure": 0}

    monkeypatch.setattr(drilldown_service, "_cache_root", lambda: cache_root)
    monkeypatch.setattr(drilldown_service, "_download_dataset_zip", lambda **kwargs: tmp_path / "erp_fraud_data.zip")
    monkeypatch.setattr(drilldown_service, "validar_ficheros_esperados_joint_datasets", lambda *args, **kwargs: None)

    class _Conn:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(drilldown_service, "get_duckdb_connection", lambda path: _Conn())
    monkeypatch.setattr(drilldown_service, "_load_o2c_raw_tables_from_zip_if_needed", lambda **kwargs: {"status": "OK"})
    monkeypatch.setattr(drilldown_service, "_ensure_o2c_optional_placeholders", lambda conn: [])
    monkeypatch.setattr(
        drilldown_service,
        "_ensure_required_o2c_entities",
        lambda **kwargs: (calls.__setitem__("ensure", calls["ensure"] + 1), db_path.write_text("rebuilt-cache", encoding="utf-8"))[-1],
    )

    def _fake_table_exists(*, db_path: Path, schema_name: str, table_name: str) -> bool:
        return db_path.read_text(encoding="utf-8") == "rebuilt-cache" and table_name == "o2c_delivery"

    monkeypatch.setattr(drilldown_service, "_duckdb_table_exists", _fake_table_exists)

    out = drilldown_service._build_db_cache(
        dataset_id="ds-001",
        scope="o2c",
        dataset_key="inputs/datasets/o2c/ds-001/erp_fraud_data.zip",
        query_id="drilldown_o2c_delivery_quantity_mismatch_v1",
        settings=_settings(),
        s3_client=object(),
    )
    assert calls["ensure"] == 1
    assert out == (db_path, "o2c", "o2c_order")


def test_rf20_drilldown_service_o2c_build_cache_uses_raw_autoload(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "cache" / "ds-001" / "o2c" / "erp.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    calls = {"autoload": 0, "placeholders": 0, "ensure": 0}
    captured = {"target_tables": None}

    monkeypatch.setattr(drilldown_service, "_cache_root", lambda: tmp_path / "cache")
    monkeypatch.setattr(drilldown_service, "_download_dataset_zip", lambda **kwargs: tmp_path / "erp_fraud_data.zip")
    monkeypatch.setattr(drilldown_service, "validar_ficheros_esperados_joint_datasets", lambda *args, **kwargs: None)

    class _Conn:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(drilldown_service, "get_duckdb_connection", lambda path: _Conn())
    monkeypatch.setattr(
        drilldown_service,
        "_load_o2c_raw_tables_from_zip_if_needed",
        lambda **kwargs: (
            calls.__setitem__("autoload", calls["autoload"] + 1),
            captured.__setitem__("target_tables", kwargs.get("target_tables")),
            {"status": "OK"},
        )[-1],
    )
    monkeypatch.setattr(
        drilldown_service,
        "_ensure_o2c_optional_placeholders",
        lambda conn: calls.__setitem__("placeholders", calls["placeholders"] + 1) or [],
    )
    monkeypatch.setattr(
        drilldown_service,
        "_ensure_required_o2c_entities",
        lambda **kwargs: calls.__setitem__("ensure", calls["ensure"] + 1) or None,
    )
    monkeypatch.setattr(drilldown_service, "_duckdb_table_exists", lambda **kwargs: True)

    out = drilldown_service._build_db_cache(
        dataset_id="ds-001",
        scope="o2c",
        dataset_key="inputs/datasets/o2c/ds-001/erp_fraud_data.zip",
        query_id="drilldown_o2c_delivery_quantity_mismatch_v1",
        settings=_settings(),
        s3_client=object(),
    )
    assert calls == {"autoload": 1, "placeholders": 1, "ensure": 1}
    assert captured["target_tables"] == ["LIPS"]
    assert out == (db_path, "o2c", "o2c_order")


def test_rf20_drilldown_service_o2c_query_id_maps_expected_required_tables() -> None:
    assert drilldown_service._required_o2c_tables_for_query_id("drilldown_o2c_delivery_quantity_mismatch_v1") == {"o2c_delivery"}
    assert drilldown_service._required_o2c_tables_for_query_id("drilldown_o2c_clearing_anomaly_v1") == {"o2c_collection"}
    assert drilldown_service._required_o2c_tables_for_query_id("drilldown_o2c_invoice_amount_anomaly_v1") == {"o2c_invoice"}


def test_rf20_drilldown_service_builds_only_required_o2c_entity(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "erp.duckdb"
    db_path.write_text("db", encoding="utf-8")
    created_entities = []

    class _Conn:
        def __init__(self) -> None:
            self.tables = {("main", "lips")}

        def execute(self, query: str, params=None):
            normalized = " ".join(query.split()).lower()
            if normalized.startswith("create schema if not exists"):
                self._fetchone = None
                return self
            if "from information_schema.tables" in normalized:
                schema_name, table_name = params
                self._fetchone = (1,) if (str(schema_name).lower(), str(table_name).lower()) in self.tables else None
                return self
            self._fetchone = None
            return self

        def fetchone(self):
            return self._fetchone

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    conn = _Conn()
    monkeypatch.setattr(drilldown_service, "get_duckdb_connection", lambda path: conn)
    monkeypatch.setattr(drilldown_service, "_load_yaml", lambda path: {"entities": {"o2c_delivery": {"required_source_tables": ["LIPS"]}}})
    monkeypatch.setattr(drilldown_service, "_entity_required_tables", lambda schema_cfg, entity: ["LIPS"])

    def _fake_create_or_replace_entity_table(connection, *, entity, target_schema, sql_body):
        created_entities.append(entity)
        connection.tables.add((target_schema.lower(), entity.lower()))
        return 1

    monkeypatch.setattr(drilldown_service, "_create_or_replace_entity_table", _fake_create_or_replace_entity_table)

    drilldown_service._ensure_required_o2c_entities(
        db_path=db_path,
        target_schema="o2c",
        query_id="drilldown_o2c_delivery_quantity_mismatch_v1",
    )
    assert created_entities == ["o2c_delivery"]


def test_rf20_drilldown_service_missing_required_raw_tables_returns_useful_error(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "erp.duckdb"
    db_path.write_text("db", encoding="utf-8")

    class _Conn:
        def execute(self, query: str, params=None):
            normalized = " ".join(query.split()).lower()
            if normalized.startswith("create schema if not exists"):
                self._fetchone = None
                return self
            if "from information_schema.tables" in normalized:
                self._fetchone = None
                return self
            self._fetchone = None
            return self

        def fetchone(self):
            return self._fetchone

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(drilldown_service, "get_duckdb_connection", lambda path: _Conn())
    monkeypatch.setattr(drilldown_service, "_load_yaml", lambda path: {"entities": {"o2c_order": {"required_source_tables": ["VBAK", "VBAP"]}}})
    monkeypatch.setattr(drilldown_service, "_entity_required_tables", lambda schema_cfg, entity: ["VBAK", "VBAP"])

    try:
        drilldown_service._ensure_required_o2c_entities(
            db_path=db_path,
            target_schema="o2c",
            query_id="drilldown_o2c_discount_policy_breach_v1",
        )
    except ValueError as exc:
        assert "faltan tablas raw requeridas VBAK, VBAP" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_rf20_results_service_marks_technical_explanation_errors(monkeypatch) -> None:
    artifacts = {
        "graph/graph_state.json": {"run_metadata": {"graph_status": "OK", "kb_index_status": "OK", "process_scope": "o2c"}},
        "graph/hypotheses.json": [],
        "graph/selected_tests.json": [],
        "graph/findings.json": [],
        "graph/scores.json": [],
        "graph/explanations.json": [
            {
                "test_id": "TST-O2C-ERR",
                "fraud_type": "collection_manipulation",
                "status": "ERROR",
                "summary": "TST-O2C-ERR terminó en ERROR; revisar error_summary y logs del runner.",
            }
        ],
        "graph/second_level_analysis.json": {},
    }
    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    out = load_graph_results(run_id="run-err", status="FAILED", scope="o2c", settings=_settings(), s3_client=object())
    assert out.explanations[0].attributes["technical_error"] is True


def test_rf20_results_service_synthesizes_executive_summary_when_second_level_is_deterministic(monkeypatch) -> None:
    artifacts = {
        "graph/graph_state.json": {"run_metadata": {"graph_status": "OK", "kb_index_status": "OK", "process_scope": "p2p"}},
        "graph/hypotheses.json": [],
        "graph/selected_tests.json": [],
        "graph/findings.json": [
            {
                "test_id": "TST-001",
                "fraud_type": "amount_anomaly",
                "status": "OK",
                "finding_count": 3,
                "columns": ["vendor"],
                "rows": [{"entity_key": "vendor=V01", "keys": {"vendor": "V01"}}],
            }
        ],
        "graph/scores.json": [{"final_label": "amount_anomaly", "confidence": 0.35, "evidence_summary": "summary"}],
        "graph/explanations.json": [
            {
                "test_id": "TST-001",
                "fraud_type": "amount_anomaly",
                "status": "OK",
                "summary": "Se observan importes anómalos frente al patrón habitual del proveedor V01.",
            }
        ],
        "graph/second_level_analysis.json": {
            "llm_insights": {
                "executive_summary": "Comparación RF16 completada con base determinista. Tipologías comunes detectadas: amount_anomaly."
            }
        },
    }
    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    out = load_graph_results(run_id="run-002", status="COMPLETED", scope="p2p", settings=_settings(), s3_client=object())
    assert "Comparación RF16 completada" not in str(out.executive_summary)
    assert "proveedor V01" in str(out.executive_summary)


def test_rf20_results_service_load_report_supports_real_ranking_object(monkeypatch) -> None:
    artifacts = {
        "report.json": {
            "summary": {"overall_status": "OK"},
            "ranking": {
                "row_count": 2,
                "rows": [{"entity_key": "E1"}, {"entity_key": "E2"}],
                "top_k": 10,
            },
            "test_runs": [{"test_id": "TST-001"}],
            "artifact_paths": {"report_md": "runs/x/report.md"},
            "metadata": {"process_scope": "p2p"},
        }
    }

    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    out = load_report(run_id="run-001", status="COMPLETED", scope="p2p", settings=_settings(), s3_client=object())
    assert out.overall_status == "OK"
    assert out.ranking.row_count == 2
    assert out.ranking.rows[1]["entity_key"] == "E2"
    assert out.ranking.top_k == 10
