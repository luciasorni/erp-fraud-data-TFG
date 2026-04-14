"""Capa reutilizable de IO en S3 para RF14c-08."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config.env import get_cloud_env_settings

try:
    import boto3  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - cubierto por tests con client inyectado
    boto3 = None


def parse_s3_uri(uri: str, *, allow_empty_prefix: bool = True) -> tuple[str, str]:
    """Parsea `s3://bucket/prefix` en (`bucket`, `prefix`)."""
    raw = str(uri or "").strip()
    if not raw.startswith("s3://"):
        raise ValueError(f"S3 URI inválida (debe empezar por s3://): {uri!r}")
    without_scheme = raw[5:]
    if not without_scheme:
        raise ValueError(f"S3 URI inválida (falta bucket): {uri!r}")

    if "/" in without_scheme:
        bucket, prefix = without_scheme.split("/", 1)
    else:
        bucket, prefix = without_scheme, ""

    bucket = bucket.strip()
    prefix = prefix.strip()
    if not bucket:
        raise ValueError(f"S3 URI inválida (bucket vacío): {uri!r}")
    if not allow_empty_prefix and not prefix:
        raise ValueError(f"S3 URI inválida (prefix vacío no permitido): {uri!r}")
    return bucket, prefix


def create_s3_client(*, region_name: str | None = None) -> Any:
    """Crea cliente S3 boto3."""
    if boto3 is None:
        raise ModuleNotFoundError("boto3 no está instalado. Instala boto3 para usar S3 IO.")
    return boto3.client("s3", region_name=region_name)


def _join_s3_key(prefix: str, relative_path: str) -> str:
    pfx = str(prefix or "").strip().strip("/")
    rel = str(relative_path or "").strip().strip("/")
    if not pfx:
        return rel
    if not rel:
        return pfx
    return f"{pfx}/{rel}"


def download_s3_prefix_to_local_dir(
    *,
    s3_uri: str,
    local_dir: str | Path,
    s3_client: Any | None = None,
) -> dict[str, Any]:
    """Descarga todos los objetos bajo prefijo S3 manteniendo ruta relativa."""
    bucket, prefix = parse_s3_uri(s3_uri, allow_empty_prefix=True)
    dest = Path(local_dir)
    dest.mkdir(parents=True, exist_ok=True)

    client = s3_client or create_s3_client(region_name=get_cloud_env_settings()["aws_region"])
    paginator = client.get_paginator("list_objects_v2")
    downloaded_files: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            key = str(obj.get("Key", "")).strip()
            if not key or key.endswith("/"):
                continue
            relative = key
            if prefix and key.startswith(prefix):
                relative = key[len(prefix) :]
            relative = relative.lstrip("/")
            if not relative:
                continue
            local_path = dest / relative
            local_path.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(local_path))
            downloaded_files.append(str(local_path))

    return {
        "bucket": bucket,
        "prefix": prefix,
        "local_dir": str(dest),
        "downloaded_files": downloaded_files,
        "downloaded_count": len(downloaded_files),
    }


def upload_local_dir_to_s3_prefix(
    *,
    local_dir: str | Path,
    s3_uri: str,
    s3_client: Any | None = None,
) -> dict[str, Any]:
    """Sube todos los ficheros de un directorio local a prefijo S3 manteniendo ruta relativa."""
    src = Path(local_dir)
    if not src.exists():
        raise FileNotFoundError(f"No existe local_dir: {src}")
    if not src.is_dir():
        raise NotADirectoryError(f"local_dir no es directorio: {src}")

    bucket, prefix = parse_s3_uri(s3_uri, allow_empty_prefix=True)
    client = s3_client or create_s3_client(region_name=get_cloud_env_settings()["aws_region"])

    uploaded_keys: list[str] = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        key = _join_s3_key(prefix, rel)
        client.upload_file(str(path), bucket, key)
        uploaded_keys.append(key)

    return {
        "bucket": bucket,
        "prefix": prefix,
        "local_dir": str(src),
        "uploaded_keys": uploaded_keys,
        "uploaded_count": len(uploaded_keys),
    }


def download_required_inputs(
    *,
    local_input_dir: str | Path,
    s3_input_uri: str | None = None,
    s3_client: Any | None = None,
) -> dict[str, Any]:
    """Helper fino para descargar inputs requeridos desde S3."""
    uri = s3_input_uri or get_cloud_env_settings()["s3_input_uri"]
    return download_s3_prefix_to_local_dir(
        s3_uri=uri,
        local_dir=local_input_dir,
        s3_client=s3_client,
    )


def upload_run_outputs(
    *,
    local_run_dir: str | Path,
    s3_output_uri: str | None = None,
    s3_client: Any | None = None,
) -> dict[str, Any]:
    """Helper fino para subir outputs de run a S3."""
    uri = s3_output_uri or get_cloud_env_settings()["s3_output_uri"]
    return upload_local_dir_to_s3_prefix(
        local_dir=local_run_dir,
        s3_uri=uri,
        s3_client=s3_client,
    )

