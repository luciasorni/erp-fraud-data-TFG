from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from ..schemas.runs import RunCreateRequest, RunCreateResponse, RunDetailResponse, RunSummaryResponse
from .aws_service import (
    AWSAPISettings,
    create_ecs_client,
    create_s3_client,
    describe_task_status,
    get_json_from_s3,
    list_s3_common_prefixes,
    load_aws_api_settings,
    run_output_key,
    runs_prefix,
    submit_graph_run_task,
    write_run_submission_record,
)
from .datasets_service import ensure_dataset_supports_scope, get_dataset


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _make_run_id(*, scope: str) -> str:
    return f"api-{scope}-graph-{_utc_now().strftime('%Y%m%d-%H%M%S')}"


def _scopes_for_request(scope: str) -> list[str]:
    if scope == "both":
        return ["p2p", "o2c"]
    return [scope]


def _dataset_input_path(*, dataset_id: str, scope: str) -> str:
    return f"datasets/{scope}/{dataset_id}/erp_fraud_data.zip"


def create_run(
    *,
    payload: RunCreateRequest,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
    ecs_client: Any | None = None,
) -> RunCreateResponse:
    client_s3 = s3_client or create_s3_client(settings=settings)
    client_ecs = ecs_client or create_ecs_client(settings=settings)
    dataset = get_dataset(dataset_id=payload.dataset_id, settings=settings, s3_client=client_s3)
    if dataset is None:
        raise ValueError(f"dataset_id no encontrado: {payload.dataset_id}")
    ensure_dataset_supports_scope(dataset=dataset, scope=payload.scope)

    submitted_at = _utc_now()
    if payload.scope == "both":
        run_ids: dict[str, str] = {}
        task_arns: dict[str, str] = {}
        for scope in ("p2p", "o2c"):
            run_id = _make_run_id(scope=scope)
            task_arn = submit_graph_run_task(
                run_id=run_id,
                process_scope=scope,
                process_family=scope,
                dataset_input_zip=_dataset_input_path(dataset_id=payload.dataset_id, scope=scope),
                llm_mode=payload.llm_mode,
                kb_index_enabled=payload.kb_index_enabled,
                settings=settings,
                ecs_client=client_ecs,
            )
            write_run_submission_record(
                run_id=run_id,
                payload={
                    "run_id": run_id,
                    "dataset_id": payload.dataset_id,
                    "scope": scope,
                    "pipeline_mode": payload.pipeline_mode,
                    "llm_mode": payload.llm_mode,
                    "kb_index_enabled": payload.kb_index_enabled,
                    "task_arn": task_arn,
                    "submitted_at_utc": submitted_at.isoformat(),
                    "composite_run": True,
                },
                settings=settings,
                s3_client=client_s3,
            )
            run_ids[scope] = run_id
            task_arns[scope] = task_arn
        return RunCreateResponse(
            composite_run=True,
            submitted_at_utc=submitted_at,
            dataset_id=payload.dataset_id,
            scope=payload.scope,
            pipeline_mode=payload.pipeline_mode,
            llm_mode=payload.llm_mode,
            kb_index_enabled=payload.kb_index_enabled,
            run_ids=run_ids,  # type: ignore[arg-type]
            task_arns=task_arns,  # type: ignore[arg-type]
        )

    run_id = _make_run_id(scope=payload.scope)
    task_arn = submit_graph_run_task(
        run_id=run_id,
        process_scope=payload.scope,
        process_family=payload.scope,
        dataset_input_zip=_dataset_input_path(dataset_id=payload.dataset_id, scope=payload.scope),
        llm_mode=payload.llm_mode,
        kb_index_enabled=payload.kb_index_enabled,
        settings=settings,
        ecs_client=client_ecs,
    )
    write_run_submission_record(
        run_id=run_id,
        payload={
            "run_id": run_id,
            "dataset_id": payload.dataset_id,
            "scope": payload.scope,
            "pipeline_mode": payload.pipeline_mode,
            "llm_mode": payload.llm_mode,
            "kb_index_enabled": payload.kb_index_enabled,
            "task_arn": task_arn,
            "submitted_at_utc": submitted_at.isoformat(),
            "composite_run": False,
        },
        settings=settings,
        s3_client=client_s3,
    )
    return RunCreateResponse(
        composite_run=False,
        submitted_at_utc=submitted_at,
        dataset_id=payload.dataset_id,
        scope=payload.scope,
        pipeline_mode=payload.pipeline_mode,
        llm_mode=payload.llm_mode,
        kb_index_enabled=payload.kb_index_enabled,
        run_id=run_id,
        task_arn=task_arn,
    )


def _load_run_api_request(
    *,
    run_id: str,
    settings: AWSAPISettings,
    s3_client: Any,
) -> dict[str, Any] | None:
    bucket, _ = runs_prefix(settings=settings)
    return get_json_from_s3(
        bucket=bucket,
        key=run_output_key(run_id=run_id, relative_path="api_request.json", settings=settings),
        settings=settings,
        s3_client=s3_client,
    )


def _load_run_metadata(
    *,
    run_id: str,
    settings: AWSAPISettings,
    s3_client: Any,
) -> dict[str, Any] | None:
    bucket, _ = runs_prefix(settings=settings)
    return get_json_from_s3(
        bucket=bucket,
        key=run_output_key(run_id=run_id, relative_path="run_metadata.json", settings=settings),
        settings=settings,
        s3_client=s3_client,
    )


def _load_graph_state(
    *,
    run_id: str,
    settings: AWSAPISettings,
    s3_client: Any,
) -> dict[str, Any] | None:
    bucket, _ = runs_prefix(settings=settings)
    return get_json_from_s3(
        bucket=bucket,
        key=run_output_key(run_id=run_id, relative_path="graph/graph_state.json", settings=settings),
        settings=settings,
        s3_client=s3_client,
    )


def _compute_run_status(
    *,
    api_request: dict[str, Any] | None,
    run_metadata: dict[str, Any] | None,
    graph_state: dict[str, Any] | None,
    settings: AWSAPISettings,
    ecs_client: Any,
) -> tuple[str, dict[str, Any] | None]:
    if graph_state:
        meta = graph_state.get("run_metadata", {})
        if isinstance(meta, dict):
            graph_status = str(meta.get("graph_status", "")).strip().upper()
            if graph_status in {"OK", "OK_WITH_WARNINGS"}:
                return "COMPLETED", None
            if graph_status == "ABORTED":
                return "FAILED", None
    if run_metadata:
        summary = run_metadata.get("summary", {}) if isinstance(run_metadata, dict) else {}
        overall = str(summary.get("overall_status", "")).strip().upper()
        if overall == "OK":
            return "COMPLETED", None
        if overall == "ERROR":
            return "FAILED", None
    task_arn = str((api_request or {}).get("task_arn", "")).strip()
    if task_arn:
        task_status = describe_task_status(task_arn=task_arn, settings=settings, ecs_client=ecs_client)
        last = str(task_status.get("last_status", "")).strip().upper()
        exit_code = task_status.get("exit_code")
        if last in {"PROVISIONING", "PENDING", "RUNNING"}:
            return "RUNNING", task_status
        if last == "STOPPED" and exit_code == 0:
            return "COMPLETED", task_status
        if last == "STOPPED":
            return "FAILED", task_status
    return "SUBMITTED", None


def get_run(
    *,
    run_id: str,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
    ecs_client: Any | None = None,
) -> RunDetailResponse | None:
    client_s3 = s3_client or create_s3_client(settings=settings)
    client_ecs = ecs_client or create_ecs_client(settings=settings)
    api_request = _load_run_api_request(run_id=run_id, settings=settings, s3_client=client_s3)
    run_metadata = _load_run_metadata(run_id=run_id, settings=settings, s3_client=client_s3)
    graph_state = _load_graph_state(run_id=run_id, settings=settings, s3_client=client_s3)
    if api_request is None and run_metadata is None and graph_state is None:
        return None
    graph_meta = graph_state.get("run_metadata", {}) if isinstance(graph_state, dict) else {}
    graph_meta = graph_meta if isinstance(graph_meta, dict) else {}
    status, task_status = _compute_run_status(
        api_request=api_request,
        run_metadata=run_metadata,
        graph_state=graph_state,
        settings=settings,
        ecs_client=client_ecs,
    )
    task_arn = str((api_request or {}).get("task_arn", "")).strip() or None
    metadata = {}
    if isinstance(run_metadata, dict):
        metadata.update(run_metadata)
    if graph_meta:
        metadata["graph_run_metadata"] = graph_meta
    artifact_keys = {
        "run_metadata_json": run_output_key(run_id=run_id, relative_path="run_metadata.json", settings=settings),
        "graph_state_json": run_output_key(run_id=run_id, relative_path="graph/graph_state.json", settings=settings),
        "report_json": run_output_key(run_id=run_id, relative_path="report.json", settings=settings),
    }
    created_at_raw = (api_request or {}).get("submitted_at_utc")
    updated_at_raw = graph_meta.get("updated_at_utc") or created_at_raw
    return RunDetailResponse(
        run_id=run_id,
        dataset_id=str((api_request or {}).get("dataset_id", "")).strip() or None,
        scope=str((api_request or {}).get("scope", "")).strip() or str(graph_meta.get("process_scope", "")).strip() or None,
        pipeline_mode=str((api_request or {}).get("pipeline_mode", "")).strip() or None,
        llm_mode=str((api_request or {}).get("llm_mode", "")).strip() or str(graph_meta.get("llm_mode", "")).strip() or None,
        kb_index_enabled=(api_request or {}).get("kb_index_enabled"),
        kb_index_status=str(graph_meta.get("kb_index_status", "")).strip() or None,
        status=status,
        graph_status=str(graph_meta.get("graph_status", "")).strip() or None,
        task_arn=task_arn,
        task_status=task_status,
        created_at_utc=datetime.fromisoformat(str(created_at_raw)) if created_at_raw else None,
        updated_at_utc=datetime.fromisoformat(str(updated_at_raw)) if updated_at_raw else None,
        metadata=metadata,
        artifact_keys=artifact_keys,
        process_family=str(graph_meta.get("process_family", "")).strip() or str((api_request or {}).get("scope", "")).strip() or None,
    )


def list_runs(
    *,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
    ecs_client: Any | None = None,
) -> list[RunSummaryResponse]:
    client_s3 = s3_client or create_s3_client(settings=settings)
    client_ecs = ecs_client or create_ecs_client(settings=settings)
    bucket, prefix = runs_prefix(settings=settings)
    base_prefix = prefix.rstrip("/") + "/"
    run_prefixes = list_s3_common_prefixes(bucket=bucket, prefix=base_prefix, settings=settings, s3_client=client_s3)
    out: list[RunSummaryResponse] = []
    for item in sorted(run_prefixes):
        run_id = item[len(base_prefix) :].strip("/ ")
        if not run_id:
            continue
        detail = get_run(run_id=run_id, settings=settings, s3_client=client_s3, ecs_client=client_ecs)
        if detail is None:
            continue
        out.append(
            RunSummaryResponse(
                run_id=detail.run_id,
                dataset_id=detail.dataset_id,
                scope=detail.scope,
                pipeline_mode=detail.pipeline_mode,
                llm_mode=detail.llm_mode,
                kb_index_enabled=detail.kb_index_enabled,
                status=detail.status,
                graph_status=detail.graph_status,
                kb_index_status=detail.kb_index_status,
                process_family=detail.process_family,
                task_arn=detail.task_arn,
                created_at_utc=detail.created_at_utc,
                updated_at_utc=detail.updated_at_utc,
            )
        )
    return sorted(out, key=lambda item: item.created_at_utc or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

