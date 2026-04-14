from __future__ import annotations

import pytest

from src.erp_fraud.config.env import (
    get_cloud_env_settings,
    parse_bool_env,
    validate_process_scope,
    validate_run_mode,
)


def test_rf14c07_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "AWS_REGION",
        "RUN_MODE",
        "S3_INPUT_URI",
        "S3_OUTPUT_URI",
        "S3_STATE_URI",
        "PROCESS_SCOPE",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = get_cloud_env_settings()
    assert settings["aws_region"] == "eu-west-1"
    assert settings["run_mode"] == "local"
    assert settings["s3_input_uri"] == "s3://tfg-fraud-dev-euw1-lucia01/inputs/"
    assert settings["s3_output_uri"] == "s3://tfg-fraud-dev-euw1-lucia01/runs/"
    assert settings["s3_state_uri"] == "s3://tfg-fraud-dev-euw1-lucia01/state/"
    assert settings["process_scope"] == "p2p"
    assert settings["langsmith_tracing"] is False
    assert settings["langsmith_project"] == "erp-fraud-tfg"


def test_rf14c07_valid_run_mode() -> None:
    assert validate_run_mode("local") == "local"
    assert validate_run_mode("CLOUD") == "cloud"


def test_rf14c07_invalid_run_mode() -> None:
    with pytest.raises(ValueError, match="RUN_MODE inválido"):
        validate_run_mode("invalid")


def test_rf14c07_valid_process_scope() -> None:
    assert validate_process_scope("p2p") == "p2p"
    assert validate_process_scope("O2C") == "o2c"
    assert validate_process_scope("both") == "both"


def test_rf14c07_invalid_process_scope() -> None:
    with pytest.raises(ValueError, match="PROCESS_SCOPE inválido"):
        validate_process_scope("sales")


def test_rf14c07_parse_langsmith_tracing() -> None:
    assert parse_bool_env("true") is True
    assert parse_bool_env("1") is True
    assert parse_bool_env("false") is False
    assert parse_bool_env("0") is False
    assert parse_bool_env(True) is True
    assert parse_bool_env(False) is False
