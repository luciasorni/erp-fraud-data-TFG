"""Configuración centralizada de variables de entorno (RF14c-07)."""

from __future__ import annotations

import os
from typing import Any

from .run_defaults import (
    DEFAULT_AWS_REGION,
    DEFAULT_LANGSMITH_PROJECT,
    DEFAULT_LANGSMITH_TRACING,
    DEFAULT_PROCESS_SCOPE,
    DEFAULT_RUN_MODE,
    DEFAULT_S3_INPUT_URI,
    DEFAULT_S3_OUTPUT_URI,
    DEFAULT_S3_STATE_URI,
)

VALID_RUN_MODES = {"local", "cloud"}
VALID_PROCESS_SCOPES = {"p2p", "o2c", "both"}


def parse_bool_env(raw_value: Any, default: bool = False) -> bool:
    """Parsea bool desde env/strings comunes."""
    if raw_value is None:
        return bool(default)
    if isinstance(raw_value, bool):
        return raw_value
    value = str(raw_value).strip().lower()
    if not value:
        return bool(default)
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def validate_run_mode(raw_value: Any) -> str:
    value = str(raw_value if raw_value is not None else DEFAULT_RUN_MODE).strip().lower()
    if value not in VALID_RUN_MODES:
        raise ValueError(f"RUN_MODE inválido: {raw_value!r}. Valores válidos: local|cloud")
    return value


def validate_process_scope(raw_value: Any) -> str:
    value = str(raw_value if raw_value is not None else DEFAULT_PROCESS_SCOPE).strip().lower()
    if value not in VALID_PROCESS_SCOPES:
        raise ValueError(f"PROCESS_SCOPE inválido: {raw_value!r}. Valores válidos: p2p|o2c|both")
    return value


def get_cloud_env_settings() -> dict[str, Any]:
    """Lee/normaliza variables cloud/langsmith relevantes para runtime."""
    aws_region = str(os.getenv("AWS_REGION", DEFAULT_AWS_REGION)).strip() or DEFAULT_AWS_REGION
    run_mode = validate_run_mode(os.getenv("RUN_MODE", DEFAULT_RUN_MODE))
    s3_input_uri = str(os.getenv("S3_INPUT_URI", DEFAULT_S3_INPUT_URI)).strip() or DEFAULT_S3_INPUT_URI
    s3_output_uri = str(os.getenv("S3_OUTPUT_URI", DEFAULT_S3_OUTPUT_URI)).strip() or DEFAULT_S3_OUTPUT_URI
    s3_state_uri = str(os.getenv("S3_STATE_URI", DEFAULT_S3_STATE_URI)).strip() or DEFAULT_S3_STATE_URI
    process_scope = validate_process_scope(os.getenv("PROCESS_SCOPE", DEFAULT_PROCESS_SCOPE))
    langsmith_tracing = parse_bool_env(
        os.getenv("LANGSMITH_TRACING", DEFAULT_LANGSMITH_TRACING),
        default=DEFAULT_LANGSMITH_TRACING,
    )
    langsmith_project = (
        str(os.getenv("LANGSMITH_PROJECT", DEFAULT_LANGSMITH_PROJECT)).strip() or DEFAULT_LANGSMITH_PROJECT
    )
    return {
        "aws_region": aws_region,
        "run_mode": run_mode,
        "s3_input_uri": s3_input_uri,
        "s3_output_uri": s3_output_uri,
        "s3_state_uri": s3_state_uri,
        "process_scope": process_scope,
        "langsmith_tracing": langsmith_tracing,
        "langsmith_project": langsmith_project,
    }

