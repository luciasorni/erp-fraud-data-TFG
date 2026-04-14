from __future__ import annotations

import argparse
from pathlib import Path

from src.erp_fraud.cli import main as cli_main


def _base_settings() -> dict:
    return {
        "input_zip": "erp_fraud_data.zip",
        "run_id": "cloud-run-1",
        "out_dir": "run_results",
        "db_path": "erp.duckdb",
        "schema_name": "main",
        "table_name": "fraud_1",
        "catalog": "tests/catalog",
        "weights_config": "config/weights.yaml",
        "timeout_ms": None,
        "sample_top_n": 20,
        "top_k": None,
        "select_tests": None,
        "select_fraud_types": None,
        "select_tags": None,
        "kb_index_enabled": True,
        "kb_sources_config": "config/kb_sources.yaml",
        "kb_chunking_config": "config/kb_chunking.yaml",
        "kb_chroma_config": "config/kb_chroma.yaml",
        "llm_mode": "stub",
        "process_family": "p2p",
        "o2c_canonical_schema_config": "config/canonical_schema_o2c.yaml",
        "o2c_identity_config": "config/o2c_entity_identity.yaml",
        "o2c_mapping_config": "config/column_mapping_o2c.yaml",
        "o2c_target_schema": "o2c",
        "aws_region": "eu-west-1",
        "run_mode": "cloud",
        "s3_input_uri": "s3://bucket/inputs/",
        "s3_output_uri": "s3://bucket/runs/",
        "s3_state_uri": "s3://bucket/state/",
        "process_scope": "p2p",
    }


def test_rf14c11_dispatcher_local_mode_routes_to_local(monkeypatch) -> None:
    called = {"local": 0, "cloud": 0}

    def _fake_resolve(_args):
        payload = _base_settings()
        payload["run_mode"] = "local"
        return payload

    def _fake_local(_args, *, resolved_settings=None):
        called["local"] += 1
        assert resolved_settings is not None
        return 0

    def _fake_cloud(_args, _settings):
        called["cloud"] += 1
        return 0

    monkeypatch.setattr(cli_main, "_resolve_run_settings", _fake_resolve)
    monkeypatch.setattr(cli_main, "_run_pipeline_local", _fake_local)
    monkeypatch.setattr(cli_main, "_run_pipeline_cloud", _fake_cloud)
    out = cli_main._run_pipeline(argparse.Namespace())
    assert out == 0
    assert called["local"] == 1
    assert called["cloud"] == 0


def test_rf14c11_dispatcher_cloud_mode_routes_to_cloud(monkeypatch) -> None:
    called = {"local": 0, "cloud": 0}

    def _fake_resolve(_args):
        return _base_settings()

    def _fake_local(_args, *, resolved_settings=None):
        called["local"] += 1
        return 0

    def _fake_cloud(_args, _settings):
        called["cloud"] += 1
        return 0

    monkeypatch.setattr(cli_main, "_resolve_run_settings", _fake_resolve)
    monkeypatch.setattr(cli_main, "_run_pipeline_local", _fake_local)
    monkeypatch.setattr(cli_main, "_run_pipeline_cloud", _fake_cloud)
    out = cli_main._run_pipeline(argparse.Namespace())
    assert out == 0
    assert called["local"] == 0
    assert called["cloud"] == 1


def test_rf14c11_cloud_flow_success_download_upload_and_state(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    settings["process_scope"] = "both"
    calls = {"download": 0, "upload": 0, "write_state": 0}

    class _FakeTmpDir:
        def __init__(self, path: Path) -> None:
            self.name = str(path)

        def cleanup(self) -> None:
            return None

    def _fake_tmpdir(prefix: str):
        return _FakeTmpDir(tmp_path / "ws")

    def _fake_download(*, local_input_dir, s3_input_uri):
        calls["download"] += 1
        p = Path(local_input_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "erp_fraud_data.zip").write_bytes(b"zip")

    def _fake_resolve_input(*, workspace_dir, requested_input_zip):
        return Path(workspace_dir) / "erp_fraud_data.zip"

    def _fake_compute_artifact_hash(*, project_root, process_scope):
        return {"artifact_hash": "ahash123", "file_count": 5}

    def _fake_read_state(**kwargs):
        return None

    def _fake_execute_local(*, inner_args, resolved_settings):
        assert resolved_settings["process_scope"] == "both"
        run_dir = Path.cwd() / "run_results" / "cloud-run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        return 0

    def _fake_upload(*, local_run_dir, s3_output_uri):
        calls["upload"] += 1
        assert str(s3_output_uri).endswith("/cloud-run-1/")
        assert Path(local_run_dir).name == "cloud-run-1"

    def _fake_write_state(**kwargs):
        calls["write_state"] += 1
        assert kwargs["last_artifact_hash"] == "ahash123"
        assert kwargs["last_run_id"] == "cloud-run-1"
        assert kwargs["process_scope"] == "both"

    monkeypatch.setattr(cli_main.tempfile, "TemporaryDirectory", _fake_tmpdir)
    monkeypatch.setattr(cli_main, "download_required_inputs", _fake_download)
    monkeypatch.setattr(cli_main, "_resolve_cloud_input_zip_path", _fake_resolve_input)
    monkeypatch.setattr(cli_main, "compute_artifact_hash", _fake_compute_artifact_hash)
    monkeypatch.setattr(cli_main, "read_last_artifact_hash_state", _fake_read_state)
    monkeypatch.setattr(cli_main, "_execute_local_pipeline_in_workspace", _fake_execute_local)
    monkeypatch.setattr(cli_main, "upload_run_outputs", _fake_upload)
    monkeypatch.setattr(cli_main, "write_last_artifact_hash_state", _fake_write_state)
    monkeypatch.setattr(cli_main, "_restore_cloud_red_flags_mapping", lambda **kwargs: None)
    out = cli_main._run_pipeline_cloud(argparse.Namespace(), settings)
    assert out == 0
    assert calls["download"] == 1
    assert calls["upload"] == 1
    assert calls["write_state"] == 1


def test_rf14c11_cloud_flow_failure_does_not_update_state(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    calls = {"write_state": 0, "upload": 0}

    class _FakeTmpDir:
        def __init__(self, path: Path) -> None:
            self.name = str(path)

        def cleanup(self) -> None:
            return None

    monkeypatch.setattr(cli_main.tempfile, "TemporaryDirectory", lambda prefix: _FakeTmpDir(tmp_path / "ws_fail"))
    monkeypatch.setattr(
        cli_main,
        "download_required_inputs",
        lambda **kwargs: (Path(kwargs["local_input_dir"]).mkdir(parents=True, exist_ok=True)),
    )
    monkeypatch.setattr(
        cli_main,
        "_resolve_cloud_input_zip_path",
        lambda **kwargs: (Path(kwargs["workspace_dir"]) / "erp_fraud_data.zip"),
    )
    monkeypatch.setattr(cli_main, "compute_artifact_hash", lambda **kwargs: {"artifact_hash": "ahashX"})
    monkeypatch.setattr(cli_main, "read_last_artifact_hash_state", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_execute_local_pipeline_in_workspace", lambda **kwargs: 2)
    monkeypatch.setattr(cli_main, "upload_run_outputs", lambda **kwargs: calls.__setitem__("upload", 1))
    monkeypatch.setattr(
        cli_main,
        "write_last_artifact_hash_state",
        lambda **kwargs: calls.__setitem__("write_state", 1),
    )
    monkeypatch.setattr(cli_main, "_restore_cloud_red_flags_mapping", lambda **kwargs: None)
    out = cli_main._run_pipeline_cloud(argparse.Namespace(), settings)
    assert out == 2
    assert calls["upload"] == 0
    assert calls["write_state"] == 0


def test_rf14c11_cloud_restores_red_flags_mapping_from_scope(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    requested_uris: list[str] = []

    def _fake_download_prefix(*, s3_uri, local_dir):
        requested_uris.append(str(s3_uri))
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        if str(s3_uri).endswith("/artifacts/mappings/p2p/"):
            (path / "red_flags_mapping.yaml").write_text("red_flags: []\n", encoding="utf-8")
            return {"downloaded_count": 1}
        return {"downloaded_count": 0}

    monkeypatch.setattr(cli_main, "download_s3_prefix_to_local_dir", _fake_download_prefix)

    restored = cli_main._restore_cloud_red_flags_mapping(
        workspace_dir=workspace,
        settings=settings,
        process_scope="p2p",
    )

    assert restored == workspace / "config" / "red_flags_mapping.yaml"
    assert restored is not None and restored.exists()
    assert restored.read_text(encoding="utf-8").strip() == "red_flags: []"
    assert requested_uris[0] == "s3://bucket/artifacts/mappings/p2p/"
