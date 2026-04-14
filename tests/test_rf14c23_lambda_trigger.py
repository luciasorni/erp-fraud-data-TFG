from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _install_fake_aws_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        def get_paginator(self, _name: str):
            class _Paginator:
                def paginate(self, **_kwargs):
                    return []

            return _Paginator()

        def get_object(self, **_kwargs):
            raise RuntimeError("get_object should be mocked in test")

        def run_task(self, **_kwargs):
            raise RuntimeError("run_task should be mocked in test")

    class _FakeBoto3Module:
        @staticmethod
        def client(_service_name: str):
            return _FakeClient()

    class _FakeClientError(Exception):
        def __init__(self, error_response=None, operation_name: str = ""):
            super().__init__(operation_name)
            self.response = error_response or {"Error": {"Code": "MockError"}}

    fake_botocore_exceptions = ModuleType("botocore.exceptions")
    setattr(fake_botocore_exceptions, "ClientError", _FakeClientError)
    fake_botocore = ModuleType("botocore")
    setattr(fake_botocore, "exceptions", fake_botocore_exceptions)

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3Module())
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)


def _load_lambda_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("BUCKET_NAME", "demo-bucket")
    monkeypatch.setenv("CLUSTER_ARN", "arn:aws:ecs:eu-west-1:111:cluster/demo")
    monkeypatch.setenv("TASK_DEF_ARN", "arn:aws:ecs:eu-west-1:111:task-definition/demo:1")
    monkeypatch.setenv("SUBNETS", "subnet-a,subnet-b")
    monkeypatch.setenv("SECURITY_GROUPS", "sg-a")
    monkeypatch.setenv("PROCESS_SCOPE", "p2p")
    _install_fake_aws_modules(monkeypatch)

    path = Path("lambda/rf14c23/lambda_function.py")
    spec = importlib.util.spec_from_file_location("rf14c23_lambda_function_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rf14c23_lambda_ignored_different_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_lambda_module(monkeypatch)
    out = mod.lambda_handler(
        {"detail": {"bucket": {"name": "other-bucket"}, "object": {"key": "artifacts/mappings/p2p/x.yaml"}}},
        None,
    )
    assert out["action"] == "ignored"
    assert out["reason"] == "different_bucket"


def test_rf14c23_lambda_ignored_non_watched_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_lambda_module(monkeypatch)
    out = mod.lambda_handler(
        {"detail": {"bucket": {"name": "demo-bucket"}, "object": {"key": "runs/run-1/report.json"}}},
        None,
    )
    assert out["action"] == "ignored"
    assert out["reason"] == "prefix_not_watched"


def test_rf14c23_lambda_skips_when_artifact_hash_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_lambda_module(monkeypatch)
    calls = {"launch": 0}

    monkeypatch.setattr(mod, "compute_artifact_hash", lambda: ("hash-1", [{"key": "a"}]))
    monkeypatch.setattr(mod, "read_previous_hash", lambda: "hash-1")

    def _fake_launch():
        calls["launch"] += 1
        return {"tasks": [{"taskArn": "arn:task/1"}]}

    monkeypatch.setattr(mod, "launch_ecs", _fake_launch)
    out = mod.lambda_handler(
        {"detail": {"bucket": {"name": "demo-bucket"}, "object": {"key": "artifacts/mappings/p2p/x.yaml"}}},
        None,
    )
    assert out["action"] == "skipped"
    assert out["reason"] == "artifact_hash_unchanged"
    assert calls["launch"] == 0


def test_rf14c23_lambda_launches_when_artifact_hash_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_lambda_module(monkeypatch)

    monkeypatch.setattr(mod, "compute_artifact_hash", lambda: ("hash-new", [{"key": "k1"}, {"key": "k2"}]))
    monkeypatch.setattr(mod, "read_previous_hash", lambda: "hash-old")
    monkeypatch.setattr(mod, "launch_ecs", lambda: {"tasks": [{"taskArn": "arn:task/2"}]})

    out = mod.lambda_handler(
        {"detail": {"bucket": {"name": "demo-bucket"}, "object": {"key": "artifacts/prompts/shared/p.md"}}},
        None,
    )
    assert out["action"] == "launched"
    assert out["artifact_hash"] == "hash-new"
    assert out["taskArns"] == ["arn:task/2"]
    assert out["manifest_count"] == 2


def test_rf14c23_lambda_state_key_uses_process_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_lambda_module(monkeypatch)
    assert mod.STATE_KEY == "state/p2p/last_artifact_hash.json"
    assert mod.PROCESS_SCOPE == "p2p"
