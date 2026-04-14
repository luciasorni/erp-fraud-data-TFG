"""State store mínimo en S3 para RF14c-10."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from ..config.env import get_cloud_env_settings, validate_process_scope
from .s3_io import create_s3_client, parse_s3_uri

try:
    from botocore.exceptions import ClientError  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - tests usan fake client
    ClientError = Exception


STATE_FILENAME = "last_artifact_hash.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_state_s3_location(
    *,
    process_scope: str | None = None,
    s3_state_uri: str | None = None,
) -> dict[str, str]:
    """Construye ubicación de estado en S3 por scope."""
    env = get_cloud_env_settings()
    scope = validate_process_scope(process_scope or env["process_scope"])
    base_uri = str(s3_state_uri or env["s3_state_uri"]).strip()
    bucket, base_prefix = parse_s3_uri(base_uri, allow_empty_prefix=True)

    prefix = str(base_prefix).strip("/")
    key = f"{scope}/{STATE_FILENAME}" if not prefix else f"{prefix}/{scope}/{STATE_FILENAME}"
    uri = f"s3://{bucket}/{key}"
    return {"bucket": bucket, "key": key, "uri": uri, "process_scope": scope}


def read_last_artifact_hash_state(
    *,
    process_scope: str | None = None,
    s3_state_uri: str | None = None,
    s3_client: Any | None = None,
) -> dict[str, Any] | None:
    """Lee estado previo. Si no existe, devuelve None (no fatal)."""
    loc = build_state_s3_location(process_scope=process_scope, s3_state_uri=s3_state_uri)
    env = get_cloud_env_settings()
    client = s3_client or create_s3_client(region_name=env["aws_region"])
    try:
        response = client.get_object(Bucket=loc["bucket"], Key=loc["key"])
    except ClientError as exc:
        error_code = str((getattr(exc, "response", {}) or {}).get("Error", {}).get("Code", "")).strip()
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise
    except Exception as exc:
        message = str(exc)
        if "NoSuchKey" in message or "NotFound" in message:
            return None
        raise

    body = response.get("Body")
    if body is None:
        return None
    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, bytes):
        payload = json.loads(raw.decode("utf-8"))
    else:
        payload = json.loads(str(raw))
    if not isinstance(payload, dict):
        raise ValueError("Estado inválido: se esperaba objeto JSON")
    return payload


def write_last_artifact_hash_state(
    *,
    last_artifact_hash: str,
    last_run_id: str,
    process_scope: str | None = None,
    s3_state_uri: str | None = None,
    updated_at: str | None = None,
    s3_client: Any | None = None,
) -> dict[str, Any]:
    """Escribe/sobrescribe el estado actual de artifact hash."""
    loc = build_state_s3_location(process_scope=process_scope, s3_state_uri=s3_state_uri)
    env = get_cloud_env_settings()
    client = s3_client or create_s3_client(region_name=env["aws_region"])
    payload: dict[str, Any] = {
        "last_artifact_hash": str(last_artifact_hash).strip(),
        "last_run_id": str(last_run_id).strip(),
        "process_scope": loc["process_scope"],
        "updated_at": str(updated_at).strip() if updated_at else _utc_now_iso(),
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    client.put_object(
        Bucket=loc["bucket"],
        Key=loc["key"],
        Body=body,
        ContentType="application/json",
    )
    return payload

