import os
import json
import hashlib
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
ecs = boto3.client("ecs")

BUCKET = os.environ["BUCKET_NAME"]
CLUSTER_ARN = os.environ["CLUSTER_ARN"]
TASK_DEF_ARN = os.environ["TASK_DEF_ARN"]
SUBNETS = os.environ["SUBNETS"].split(",")
SECURITY_GROUPS = os.environ["SECURITY_GROUPS"].split(",")
PROCESS_SCOPE = os.environ.get("PROCESS_SCOPE", "both")

WATCH_PREFIXES = [
    "artifacts/prompts/",
    "artifacts/catalogs/",
    "artifacts/mappings/",
]

STATE_KEY = f"state/{PROCESS_SCOPE}/last_artifact_hash.json"


def list_keys(prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            yield key


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_artifact_manifest():
    manifest = []
    for prefix in WATCH_PREFIXES:
        for key in sorted(list(list_keys(prefix))):
            body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
            manifest.append(
                {
                    "key": key,
                    "sha256": sha256_bytes(body),
                    "size": len(body),
                }
            )
    return manifest


def compute_artifact_hash():
    manifest = build_artifact_manifest()
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), manifest


def read_previous_hash():
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=STATE_KEY)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        return data.get("last_artifact_hash")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NoSuchKey", "404"):
            return None
        raise


def launch_ecs():
    response = ecs.run_task(
        cluster=CLUSTER_ARN,
        taskDefinition=TASK_DEF_ARN,
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": SUBNETS,
                "securityGroups": SECURITY_GROUPS,
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "erp-fraud-pipeline",
                    "command": ["run", "--input-zip", "erp_fraud_data.zip"],
                    "environment": [
                        {"name": "RUN_MODE", "value": "cloud"},
                        {"name": "PROCESS_SCOPE", "value": PROCESS_SCOPE},
                    ],
                }
            ]
        },
    )
    return response


def lambda_handler(event, context):
    # Validación básica del evento
    detail = event.get("detail", {})
    bucket_name = detail.get("bucket", {}).get("name")
    object_key = unquote_plus(detail.get("object", {}).get("key", ""))

    if bucket_name != BUCKET:
        return {"action": "ignored", "reason": "different_bucket"}

    if not any(object_key.startswith(p) for p in WATCH_PREFIXES):
        return {"action": "ignored", "reason": "prefix_not_watched", "key": object_key}

    current_hash, manifest = compute_artifact_hash()
    previous_hash = read_previous_hash()

    print(
        json.dumps(
            {
                "message": "artifact_hash_comparison",
                "trigger_key": object_key,
                "process_scope": PROCESS_SCOPE,
                "previous_hash": previous_hash,
                "current_hash": current_hash,
            }
        )
    )

    if previous_hash == current_hash:
        print(json.dumps({"message": "skip_ecs_run", "reason": "artifact_hash_unchanged"}))
        return {
            "action": "skipped",
            "reason": "artifact_hash_unchanged",
            "artifact_hash": current_hash,
        }

    response = launch_ecs()
    task_arns = [t["taskArn"] for t in response.get("tasks", [])]

    print(json.dumps({"message": "ecs_run_task_launched", "taskArns": task_arns}))

    return {
        "action": "launched",
        "artifact_hash": current_hash,
        "taskArns": task_arns,
        "manifest_count": len(manifest),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }