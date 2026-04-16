from __future__ import annotations

import io
from datetime import datetime, timezone
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.schemas.datasets import DatasetDetailResponse, DatasetSummaryResponse, DatasetUploadResponse
from app.api.schemas.drilldown import DrilldownJobResponse, DrilldownResponse
from app.api.schemas.results import GraphResultsResponse, ReportRanking, ReportResponse
from app.api.schemas.runs import RunCreateResponse, RunDetailResponse, RunSummaryResponse
from app.api.schemas.operations import OperationStatusResponse


def _client() -> TestClient:
    return TestClient(create_app())


def _valid_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        zf.writestr("erp_fraud_data/joint_datasets/README.txt", "ok\n")
        zf.writestr("erp_fraud_data/joint_datasets/column_information.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/fraud_1.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/fraud_1_expls.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/fraud_2.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/fraud_2_expls.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/fraud_3.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/fraud_3_expls.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/normal_1.csv", "a,b\n1,2\n")
        zf.writestr("erp_fraud_data/joint_datasets/normal_2.csv", "a,b\n1,2\n")
    return buffer.getvalue()


def test_rf20_health_endpoint_ok() -> None:
    response = _client().get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rf20_datasets_upload_endpoint(monkeypatch) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)

    def _fake_upload_dataset(*, file, scope, settings):
        return DatasetUploadResponse(
            dataset_id="ds-001",
            file_name=str(file.filename),
            scopes=["p2p", "o2c"],
            validation_status="VALID",
            files_detected=["README.txt", "fraud_1.csv"],
            expected_files=["README.txt", "fraud_1.csv", "normal_1.csv"],
            dataset_hash="abc123",
            uploaded_at_utc=now,
            s3_keys={"p2p": "inputs/datasets/p2p/ds-001/erp_fraud_data.zip", "o2c": "inputs/datasets/o2c/ds-001/erp_fraud_data.zip"},
            size_bytes=2048,
        )

    monkeypatch.setattr("app.api.routers.datasets.upload_dataset", _fake_upload_dataset)
    response = _client().post(
        "/api/v1/datasets/upload",
        data={"scope": "both"},
        files={"file": ("erp_fraud_data.zip", _valid_zip_bytes(), "application/zip")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == "ds-001"
    assert payload["scopes"] == ["p2p", "o2c"]
    assert payload["expected_files"] == ["README.txt", "fraud_1.csv", "normal_1.csv"]
    assert payload["size_bytes"] == 2048


def test_rf20_datasets_upload_job_endpoint(monkeypatch) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setattr(
        "app.api.routers.datasets.create_job",
        lambda **kwargs: OperationStatusResponse(
            job_id="job-upload-001",
            kind="dataset_upload",
            status="QUEUED",
            stage="queued",
            message="Dataset upload queued.",
            progress=0,
            created_at_utc=now,
            updated_at_utc=now,
            result=None,
            error=None,
        ),
    )
    monkeypatch.setattr("app.api.routers.datasets.run_job_in_thread", lambda **kwargs: None)
    response = _client().post(
        "/api/v1/datasets/upload-jobs",
        data={"scope": "both"},
        files={"file": ("erp_fraud_data.zip", _valid_zip_bytes(), "application/zip")},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"] == "job-upload-001"
    assert payload["kind"] == "dataset_upload"


def test_rf20_runs_post_supports_scope_both(monkeypatch) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)

    def _fake_create_run(*, payload, settings):
        return RunCreateResponse(
            composite_run=True,
            submitted_at_utc=now,
            dataset_id=payload.dataset_id,
            scope="both",
            pipeline_mode="graph",
            llm_mode=payload.llm_mode,
            kb_index_enabled=payload.kb_index_enabled,
            run_ids={"p2p": "run-p2p-001", "o2c": "run-o2c-001"},
            task_arns={"p2p": "task-p2p", "o2c": "task-o2c"},
        )

    monkeypatch.setattr("app.api.routers.runs.create_run", _fake_create_run)
    response = _client().post(
        "/api/v1/runs",
        json={
            "dataset_id": "ds-001",
            "scope": "both",
            "pipeline_mode": "graph",
            "llm_mode": "real",
            "kb_index_enabled": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["composite_run"] is True
    assert payload["run_ids"]["p2p"] == "run-p2p-001"
    assert payload["run_ids"]["o2c"] == "run-o2c-001"


def test_rf20_runs_list_endpoint_passes_limit(monkeypatch) -> None:
    captured = {}

    def _fake_list_runs(*, settings, limit):
        captured["limit"] = limit
        return [
            RunSummaryResponse(
                run_id="run-001",
                dataset_id="ds-001",
                scope="p2p",
                pipeline_mode="graph",
                llm_mode="real",
                kb_index_enabled=False,
                status="COMPLETED",
                graph_status="OK",
                kb_index_status="SKIPPED_NO_REBUILD",
                process_family="p2p",
                task_arn="task-001",
                created_at_utc=None,
                updated_at_utc=None,
            )
        ]

    monkeypatch.setattr("app.api.routers.runs.list_runs", _fake_list_runs)
    response = _client().get("/api/v1/runs?limit=5")
    assert response.status_code == 200
    assert captured["limit"] == 5
    assert response.json()[0]["run_id"] == "run-001"


def test_rf20_runs_graph_endpoint_returns_ui_payload(monkeypatch) -> None:
    def _fake_get_run(*, run_id, settings):
        return RunDetailResponse(
            run_id=run_id,
            dataset_id="ds-001",
            scope="p2p",
            pipeline_mode="graph",
            llm_mode="real",
            kb_index_enabled=False,
            process_family="p2p",
            kb_index_status="SKIPPED_NO_REBUILD",
            status="COMPLETED",
            graph_status="OK",
            task_arn="task-123",
            task_status=None,
            created_at_utc=None,
            updated_at_utc=None,
            metadata={},
            artifact_keys={},
        )

    def _fake_load_graph_results(*, run_id, status, scope, settings):
        return GraphResultsResponse(
            run_id=run_id,
            scope=scope,
            status=status,
            graph_status="OK",
            kb_index_status="SKIPPED_NO_REBUILD",
            counts={
                "hypotheses": 3,
                "selected_tests": 4,
                "findings": 4,
                "scores": 1,
                "explanations": 4,
                "second_level_analysis": 2,
            },
            hypotheses=[],
            selected_tests=[],
            findings=[],
            scores=[],
            explanations=[],
            second_level_analysis=[],
        )

    monkeypatch.setattr("app.api.routers.runs.get_run", _fake_get_run)
    monkeypatch.setattr("app.api.routers.runs.load_graph_results", _fake_load_graph_results)
    response = _client().get("/api/v1/runs/run-001/graph")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-001"
    assert payload["graph_status"] == "OK"
    assert payload["kb_index_status"] == "SKIPPED_NO_REBUILD"
    assert payload["counts"]["findings"] == 4


def test_rf20_runs_report_endpoint_accepts_real_ranking_shape(monkeypatch) -> None:
    def _fake_get_run(*, run_id, settings):
        return RunDetailResponse(
            run_id=run_id,
            dataset_id="ds-001",
            scope="p2p",
            pipeline_mode="graph",
            llm_mode="real",
            kb_index_enabled=False,
            process_family="p2p",
            kb_index_status="SKIPPED_NO_REBUILD",
            status="COMPLETED",
            graph_status="OK",
            task_arn="task-123",
            task_status=None,
            created_at_utc=None,
            updated_at_utc=None,
            metadata={},
            artifact_keys={},
        )

    def _fake_load_report(*, run_id, status, scope, settings):
        return ReportResponse(
            run_id=run_id,
            scope=scope,
            status=status,
            overall_status="OK",
            summary={"overall_status": "OK"},
            ranking=ReportRanking(
                row_count=2,
                rows=[{"entity_key": "A"}, {"entity_key": "B"}],
                top_k=20,
            ),
            test_runs=[],
            artifact_paths={},
            metadata={},
        )

    monkeypatch.setattr("app.api.routers.runs.get_run", _fake_get_run)
    monkeypatch.setattr("app.api.routers.runs.load_report", _fake_load_report)
    response = _client().get("/api/v1/runs/run-001/report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking"]["row_count"] == 2
    assert payload["ranking"]["rows"][0]["entity_key"] == "A"
    assert payload["ranking"]["top_k"] == 20


def test_rf20_drilldown_rejects_unknown_action_schema_level() -> None:
    response = _client().post(
        "/api/v1/runs/run-001/drilldown",
        json={
            "action": "free_sql",
            "test_id": "TST-DUPLICATE-POSTINGS",
            "keys": {"kreditor": "V1", "belegnummer": "1", "position": "1", "betrag": "10"},
        },
    )
    assert response.status_code == 422


def test_rf20_drilldown_endpoint_returns_safe_payload(monkeypatch) -> None:
    def _fake_execute_drilldown(*, run_id, payload, settings):
        assert payload.query_id == "drilldown_o2c_delivery_quantity_mismatch_v1"
        return DrilldownResponse(
            run_id=run_id,
            action=payload.action,
            test_id=payload.test_id,
            query_id="drilldown_duplicate_postings_v1",
            row_count=1,
            rows=[{"Kreditor": "V01", "Belegnummer": "5001"}],
            allowed_actions=["finding_rows"],
        )

    monkeypatch.setattr("app.api.routers.drilldown.execute_drilldown", _fake_execute_drilldown)
    response = _client().post(
        "/api/v1/runs/run-001/drilldown",
        json={
            "action": "finding_rows",
            "test_id": "TST-DUPLICATE-POSTINGS",
            "keys": {"kreditor": "V1", "belegnummer": "1", "position": "1", "betrag": "10"},
            "query_id": "drilldown_o2c_delivery_quantity_mismatch_v1",
            "limit_rows": 20,
            "order_direction": "ASC",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["query_id"] == "drilldown_duplicate_postings_v1"
    assert payload["allowed_actions"] == ["finding_rows"]


def test_rf20_drilldown_endpoint_returns_useful_error_when_keys_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.drilldown.execute_drilldown",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("Faltan keys mínimas para el test X")),
    )
    response = _client().post(
        "/api/v1/runs/run-001/drilldown",
        json={
            "action": "finding_rows",
            "test_id": "TST-O2C-CLEARING-ANOMALY",
            "keys": {"company_code": "1000"},
        },
    )
    assert response.status_code == 400
    assert "Faltan keys mínimas" in str(response.json()["detail"])


def test_rf20_drilldown_job_endpoint_returns_job_handle(monkeypatch) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setattr(
        "app.api.routers.drilldown.create_job",
        lambda **kwargs: DrilldownJobResponse(
            job_id="job-drilldown-001",
            kind="drilldown",
            status="QUEUED",
            stage="queued",
            message="Drilldown queued.",
            progress=0,
            created_at_utc=now,
            updated_at_utc=now,
            result=None,
            error=None,
        ),
    )
    monkeypatch.setattr("app.api.routers.drilldown.run_job_in_thread", lambda **kwargs: None)
    response = _client().post(
        "/api/v1/runs/run-001/drilldown-jobs",
        json={
            "action": "finding_rows",
            "test_id": "TST-DUPLICATE-POSTINGS",
            "keys": {"kreditor": "V1", "belegnummer": "1", "position": "1", "betrag": "10"},
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"] == "job-drilldown-001"
    assert payload["kind"] == "drilldown"
