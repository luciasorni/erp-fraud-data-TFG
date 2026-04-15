from __future__ import annotations

from datetime import datetime, timezone

from app.api.schemas.datasets import DatasetDetailResponse
from app.api.schemas.results import GraphResultsResponse
from app.api.schemas.runs import RunCreateRequest
from app.api.services.aws_service import AWSAPISettings
from app.api.services.results_service import load_graph_results, load_report
from app.api.services.runs_service import create_run


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
    monkeypatch.setattr("app.api.services.runs_service.write_run_submission_record", lambda **kwargs: "ok")

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
            "recommendations": [
                {
                    "title": "Review vendor V01",
                    "category": "follow_up",
                    "priority": "high",
                    "summary": "Open manual review",
                }
            ]
        },
    }

    monkeypatch.setattr(
        "app.api.services.results_service._read_json_artifact",
        lambda *, run_id, relative_path, settings, s3_client=None: artifacts.get(relative_path),
    )
    out = load_graph_results(run_id="run-001", status="COMPLETED", scope="p2p", settings=_settings(), s3_client=object())
    assert isinstance(out, GraphResultsResponse)
    assert out.counts.hypotheses == 1
    assert out.counts.selected_tests == 1
    assert out.counts.findings == 1
    assert out.counts.scores == 1
    assert out.counts.explanations == 1
    assert out.counts.second_level_analysis == 1
    assert out.hypotheses[0].title == "Amount anomaly"
    assert out.findings[0].attributes["sample_entity_key"] == "betrag=100|kreditor=V01"
    assert out.second_level_analysis[0].title == "Review vendor V01"


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
