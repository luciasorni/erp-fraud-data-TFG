from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import boto3

from src.erp_fraud.storage import parse_s3_uri


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass(frozen=True)
class AWSAPISettings:
    aws_region: str
    aws_profile: str | None
    s3_input_uri: str
    s3_output_uri: str
    ecs_cluster: str
    ecs_task_definition: str
    subnet_ids: tuple[str, ...]
    security_group_ids: tuple[str, ...]


def load_aws_api_settings() -> AWSAPISettings:
    profile = str(os.getenv("AWS_PROFILE", "")).strip() or None
    region = str(os.getenv("AWS_REGION", "eu-west-1")).strip() or "eu-west-1"
    subnet_default = (
        "subnet-091fb9bd171d238aa,"
        "subnet-00cd0a8035d8f7dd6,"
        "subnet-0329d6462aeb6fdf7"
    )
    sg_default = "sg-0bbcc120180a92672"
    return AWSAPISettings(
        aws_region=region,
        aws_profile=profile,
        s3_input_uri=str(os.getenv("S3_INPUT_URI", "s3://tfg-fraud-dev-euw1-lucia01/inputs/")).strip(),
        s3_output_uri=str(os.getenv("S3_OUTPUT_URI", "s3://tfg-fraud-dev-euw1-lucia01/runs/")).strip(),
        ecs_cluster=str(os.getenv("API_ECS_CLUSTER", "tfg-fraud-dev-ecs-cluster")).strip(),
        ecs_task_definition=str(os.getenv("API_ECS_TASK_DEFINITION", "tfg-fraud-dev-task")).strip(),
        subnet_ids=tuple(
            value.strip()
            for value in str(os.getenv("API_ECS_SUBNETS", subnet_default)).split(",")
            if value.strip()
        ),
        security_group_ids=tuple(
            value.strip()
            for value in str(os.getenv("API_ECS_SECURITY_GROUPS", sg_default)).split(",")
            if value.strip()
        ),
    )


def create_boto3_session(*, settings: AWSAPISettings | None = None) -> boto3.session.Session:
    cfg = settings or load_aws_api_settings()
    if cfg.aws_profile:
        return boto3.session.Session(profile_name=cfg.aws_profile, region_name=cfg.aws_region)
    return boto3.session.Session(region_name=cfg.aws_region)


def create_s3_client(*, settings: AWSAPISettings | None = None) -> Any:
    return create_boto3_session(settings=settings).client("s3")


def create_ecs_client(*, settings: AWSAPISettings | None = None) -> Any:
    return create_boto3_session(settings=settings).client("ecs")


def _input_bucket_prefix(*, settings: AWSAPISettings) -> tuple[str, str]:
    return parse_s3_uri(settings.s3_input_uri, allow_empty_prefix=True)


def _output_bucket_prefix(*, settings: AWSAPISettings) -> tuple[str, str]:
    return parse_s3_uri(settings.s3_output_uri, allow_empty_prefix=True)


def _join_key(prefix: str, relative: str) -> str:
    base = prefix.strip().strip("/")
    rel = relative.strip().strip("/")
    if not base:
        return rel
    if not rel:
        return base
    return f"{base}/{rel}"


def dataset_registry_key(*, dataset_id: str, settings: AWSAPISettings | None = None) -> str:
    cfg = settings or load_aws_api_settings()
    _, prefix = _input_bucket_prefix(settings=cfg)
    return _join_key(prefix, f"datasets/registry/{dataset_id}.json")


def dataset_zip_key(*, dataset_id: str, scope: str, settings: AWSAPISettings | None = None) -> str:
    cfg = settings or load_aws_api_settings()
    _, prefix = _input_bucket_prefix(settings=cfg)
    return _join_key(prefix, f"datasets/{scope}/{dataset_id}/erp_fraud_data.zip")


def put_json_to_s3(
    *,
    key: str,
    payload: dict[str, Any],
    settings: AWSAPISettings | None = None,
    s3_client: Any | None = None,
) -> str:
    cfg = settings or load_aws_api_settings()
    bucket, _ = _input_bucket_prefix(settings=cfg)
    if key.startswith(_output_bucket_prefix(settings=cfg)[1].strip("/")):
        bucket, _ = _output_bucket_prefix(settings=cfg)
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    client = s3_client or create_s3_client(settings=cfg)
    client.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"), ContentType="application/json")
    return key


def put_bytes_to_s3(
    *,
    key: str,
    body: bytes,
    content_type: str,
    settings: AWSAPISettings | None = None,
    s3_client: Any | None = None,
) -> str:
    cfg = settings or load_aws_api_settings()
    bucket, _ = _input_bucket_prefix(settings=cfg)
    client = s3_client or create_s3_client(settings=cfg)
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    return key


def get_json_from_s3(
    *,
    bucket: str,
    key: str,
    s3_client: Any | None = None,
    settings: AWSAPISettings | None = None,
) -> dict[str, Any] | None:
    cfg = settings or load_aws_api_settings()
    client = s3_client or create_s3_client(settings=cfg)
    try:
        out = client.get_object(Bucket=bucket, Key=key)
    except client.exceptions.NoSuchKey:  # type: ignore[attr-defined]
        return None
    except Exception as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if error_code in {"NoSuchKey", "404"}:
            return None
        raise
    raw = out["Body"].read().decode("utf-8")
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else None


def get_s3_text(
    *,
    bucket: str,
    key: str,
    s3_client: Any | None = None,
    settings: AWSAPISettings | None = None,
) -> str | None:
    cfg = settings or load_aws_api_settings()
    client = s3_client or create_s3_client(settings=cfg)
    try:
        out = client.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if error_code in {"NoSuchKey", "404"}:
            return None
        raise
    return out["Body"].read().decode("utf-8")


def list_s3_keys(
    *,
    bucket: str,
    prefix: str,
    s3_client: Any | None = None,
    settings: AWSAPISettings | None = None,
) -> list[str]:
    cfg = settings or load_aws_api_settings()
    client = s3_client or create_s3_client(settings=cfg)
    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            key = str(obj.get("Key", "")).strip()
            if key:
                keys.append(key)
    return keys


def list_s3_common_prefixes(
    *,
    bucket: str,
    prefix: str,
    delimiter: str = "/",
    s3_client: Any | None = None,
    settings: AWSAPISettings | None = None,
) -> list[str]:
    cfg = settings or load_aws_api_settings()
    client = s3_client or create_s3_client(settings=cfg)
    paginator = client.get_paginator("list_objects_v2")
    prefixes: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter=delimiter):
        for item in page.get("CommonPrefixes", []) or []:
            candidate = str(item.get("Prefix", "")).strip()
            if candidate:
                prefixes.append(candidate)
    return prefixes


def submit_graph_run_task(
    *,
    run_id: str,
    process_scope: str,
    process_family: str,
    dataset_input_zip: str,
    llm_mode: str,
    kb_index_enabled: bool,
    settings: AWSAPISettings | None = None,
    ecs_client: Any | None = None,
) -> str:
    cfg = settings or load_aws_api_settings()
    client = ecs_client or create_ecs_client(settings=cfg)
    command = [
        "run",
        "--input-zip",
        dataset_input_zip,
        "--run-id",
        run_id,
        "--pipeline-mode",
        "graph",
        "--process-family",
        process_family,
        "--llm-mode",
        llm_mode,
    ]
    if kb_index_enabled:
        command.append("--kb-index-enabled")
    overrides = {
        "containerOverrides": [
            {
                "name": "erp-fraud-pipeline",
                "command": command,
                "environment": [
                    {"name": "RUN_MODE", "value": "cloud"},
                    {"name": "PROCESS_SCOPE", "value": process_scope},
                ],
            }
        ]
    }
    out = client.run_task(
        cluster=cfg.ecs_cluster,
        taskDefinition=cfg.ecs_task_definition,
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": list(cfg.subnet_ids),
                "securityGroups": list(cfg.security_group_ids),
                "assignPublicIp": "ENABLED",
            }
        },
        overrides=overrides,
    )
    failures = out.get("failures", []) or []
    if failures:
        raise RuntimeError(f"ECS run_task failures: {failures}")
    tasks = out.get("tasks", []) or []
    if not tasks:
        raise RuntimeError("ECS run_task no devolvió tasks")
    return str(tasks[0].get("taskArn", "")).strip()


def describe_task_status(
    *,
    task_arn: str,
    settings: AWSAPISettings | None = None,
    ecs_client: Any | None = None,
) -> dict[str, Any]:
    cfg = settings or load_aws_api_settings()
    client = ecs_client or create_ecs_client(settings=cfg)
    out = client.describe_tasks(cluster=cfg.ecs_cluster, tasks=[task_arn])
    tasks = out.get("tasks", []) or []
    if not tasks:
        return {"status": "UNKNOWN", "task_arn": task_arn}
    task = tasks[0]
    container = (task.get("containers", []) or [{}])[0]
    return {
        "task_arn": task_arn,
        "last_status": task.get("lastStatus"),
        "desired_status": task.get("desiredStatus"),
        "stopped_reason": task.get("stoppedReason"),
        "stop_code": task.get("stopCode"),
        "exit_code": container.get("exitCode"),
        "container_reason": container.get("reason"),
    }


def runs_prefix(*, settings: AWSAPISettings | None = None) -> tuple[str, str]:
    cfg = settings or load_aws_api_settings()
    return _output_bucket_prefix(settings=cfg)


def run_output_key(*, run_id: str, relative_path: str, settings: AWSAPISettings | None = None) -> str:
    cfg = settings or load_aws_api_settings()
    _, prefix = _output_bucket_prefix(settings=cfg)
    return _join_key(prefix, f"{run_id}/{relative_path}")


def write_run_submission_record(
    *,
    run_id: str,
    payload: dict[str, Any],
    settings: AWSAPISettings | None = None,
    s3_client: Any | None = None,
) -> str:
    cfg = settings or load_aws_api_settings()
    bucket, _ = _output_bucket_prefix(settings=cfg)
    key = run_output_key(run_id=run_id, relative_path="api_request.json", settings=cfg)
    client = s3_client or create_s3_client(settings=cfg)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        ContentType="application/json",
    )
    return key

