from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import UploadFile

from src.erp_fraud.ingest import EXPECTED_JOINT_DATASET_FILES, calcular_dataset_hash, validar_ficheros_esperados_joint_datasets

from ..schemas.datasets import DatasetDetailResponse, DatasetSummaryResponse, DatasetUploadResponse
from .aws_service import (
    AWSAPISettings,
    create_s3_client,
    dataset_registry_key,
    dataset_zip_key,
    get_json_from_s3,
    list_s3_keys,
    put_bytes_to_s3,
    put_json_to_s3,
    runs_prefix,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _dataset_id_from_content(file_name: str, body: bytes) -> str:
    stem = Path(file_name).stem.strip().lower() or "dataset"
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in stem).strip("-") or "dataset"
    digest = hashlib.sha256(body).hexdigest()[:12]
    ts = _utc_now().strftime("%Y%m%d%H%M%S")
    return f"{safe}-{ts}-{digest}"


def _metadata_bucket_prefix(*, settings: AWSAPISettings) -> tuple[str, str]:
    return runs_prefix(settings=settings)


def _validate_dataset_upload(file_name: str, body: bytes) -> tuple[list[str], str]:
    with NamedTemporaryFile(suffix=".zip", delete=True) as tmp:
        tmp.write(body)
        tmp.flush()
        files_detected = validar_ficheros_esperados_joint_datasets(tmp.name)
        dataset_hash = calcular_dataset_hash(tmp.name).dataset_hash
    return files_detected, dataset_hash


def _normalize_scopes(scope: str) -> list[str]:
    value = str(scope).strip().lower()
    if value == "both":
        return ["p2p", "o2c"]
    if value in {"p2p", "o2c"}:
        return [value]
    raise ValueError("scope debe ser p2p|o2c|both")


def _registry_bucket_prefix(*, settings: AWSAPISettings) -> tuple[str, str]:
    from src.erp_fraud.storage import parse_s3_uri

    bucket, prefix = parse_s3_uri(settings.s3_input_uri, allow_empty_prefix=True)
    return bucket, prefix


def upload_dataset_from_bytes(
    *,
    file_name: str,
    body: bytes,
    scope: str,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
    status_callback: Any | None = None,
) -> DatasetUploadResponse:
    file_name = str(file_name or "").strip() or "erp_fraud_data.zip"
    if Path(file_name).suffix.lower() != ".zip":
        raise ValueError("El dataset debe ser un fichero .zip")
    if not body:
        raise ValueError("El dataset ZIP está vacío")

    if status_callback:
        status_callback(stage="validating", message="Validando estructura del ZIP...", progress=15)
    files_detected, dataset_hash = _validate_dataset_upload(file_name, body)
    dataset_id = _dataset_id_from_content(file_name, body)
    scopes = _normalize_scopes(scope)
    uploaded_at = _utc_now()
    client = s3_client or create_s3_client(settings=settings)
    s3_keys: dict[str, str] = {}
    for index, item_scope in enumerate(scopes, start=1):
        if status_callback:
            status_callback(
                stage="uploading",
                message=f"Registrando ZIP para scope={item_scope}...",
                progress=35 + int((index - 1) * 30 / max(1, len(scopes))),
            )
        zip_key = dataset_zip_key(dataset_id=dataset_id, scope=item_scope, settings=settings)
        put_bytes_to_s3(
            key=zip_key,
            body=body,
            content_type="application/zip",
            settings=settings,
            s3_client=client,
        )
        s3_keys[item_scope] = zip_key

    metadata = {
        "dataset_id": dataset_id,
        "file_name": file_name,
        "scopes": scopes,
        "validation_status": "VALID",
        "dataset_hash": dataset_hash,
        "uploaded_at_utc": uploaded_at.isoformat(),
        "files_detected": files_detected,
        "expected_files": list(EXPECTED_JOINT_DATASET_FILES),
        "size_bytes": len(body),
        "s3_keys": s3_keys,
    }
    if status_callback:
        status_callback(stage="registering", message="Registrando metadatos del dataset...", progress=85)
    registry_key = dataset_registry_key(dataset_id=dataset_id, settings=settings)
    put_json_to_s3(key=registry_key, payload=metadata, settings=settings, s3_client=client)
    if status_callback:
        status_callback(stage="completed", message="Dataset listo para análisis.", progress=100)
    return DatasetUploadResponse(**metadata)


def upload_dataset(
    *,
    file: UploadFile,
    scope: str,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
) -> DatasetUploadResponse:
    body = file.file.read()
    return upload_dataset_from_bytes(
        file_name=str(file.filename or "").strip() or "erp_fraud_data.zip",
        body=body,
        scope=scope,
        settings=settings,
        s3_client=s3_client,
    )


def _load_dataset_metadata(
    *,
    dataset_id: str,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
) -> dict[str, Any] | None:
    bucket, _ = _registry_bucket_prefix(settings=settings)
    return get_json_from_s3(
        bucket=bucket,
        key=dataset_registry_key(dataset_id=dataset_id, settings=settings),
        settings=settings,
        s3_client=s3_client,
    )


def get_dataset(
    *,
    dataset_id: str,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
) -> DatasetDetailResponse | None:
    payload = _load_dataset_metadata(dataset_id=dataset_id, settings=settings, s3_client=s3_client)
    if payload is None:
        return None
    payload["metadata_key"] = dataset_registry_key(dataset_id=dataset_id, settings=settings)
    return DatasetDetailResponse(**payload)


def list_datasets(
    *,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
) -> list[DatasetSummaryResponse]:
    bucket, prefix = _registry_bucket_prefix(settings=settings)
    registry_prefix = f"{prefix.rstrip('/')}/datasets/registry/"
    client = s3_client or create_s3_client(settings=settings)
    keys = list_s3_keys(bucket=bucket, prefix=registry_prefix, settings=settings, s3_client=client)
    out: list[DatasetSummaryResponse] = []
    for key in sorted(keys):
        if not key.endswith(".json"):
            continue
        payload = get_json_from_s3(bucket=bucket, key=key, settings=settings, s3_client=client)
        if not payload:
            continue
        out.append(
            DatasetSummaryResponse(
                dataset_id=str(payload.get("dataset_id", "")).strip(),
                file_name=str(payload.get("file_name", "")).strip(),
                scopes=list(payload.get("scopes", [])),
                validation_status=str(payload.get("validation_status", "")).strip() or "UNKNOWN",
                dataset_hash=str(payload.get("dataset_hash", "")).strip(),
                uploaded_at_utc=datetime.fromisoformat(str(payload.get("uploaded_at_utc"))),
            )
        )
    return sorted(out, key=lambda item: item.uploaded_at_utc, reverse=True)


def ensure_dataset_supports_scope(*, dataset: DatasetDetailResponse, scope: str) -> None:
    needed = _normalize_scopes(scope)
    available = set(dataset.scopes)
    missing = [item for item in needed if item not in available]
    if missing:
        raise ValueError(
            "dataset_id no disponible para los scopes requeridos: " + ", ".join(missing)
        )
