from __future__ import annotations

import argparse
import json
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
        "kb_index_cli_explicit": False,
        "kb_sources_config": "config/kb_sources.yaml",
        "kb_chunking_config": "config/kb_chunking.yaml",
        "kb_chroma_config": "config/kb_chroma.yaml",
        "llm_mode": "stub",
        "pipeline_mode": "deterministic",
        "process_family": "p2p",
        "process_family_explicit": True,
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
    monkeypatch.setattr(cli_main, "_restore_cloud_weights_config", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_catalog_dir", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_file_from_source_root", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_dir_from_source_root", lambda **kwargs: None)
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
    monkeypatch.setattr(cli_main, "_restore_cloud_weights_config", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_catalog_dir", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_file_from_source_root", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_dir_from_source_root", lambda **kwargs: None)
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


def test_rf14c11_cloud_restores_weights_from_scope(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    workspace = tmp_path / "ws_weights"
    workspace.mkdir(parents=True, exist_ok=True)
    requested_uris: list[str] = []

    def _fake_download_prefix(*, s3_uri, local_dir):
        requested_uris.append(str(s3_uri))
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        if str(s3_uri).endswith("/artifacts/mappings/p2p/"):
            (path / "weights.yaml").write_text("defaults:\n  fallback_weight: 1\n", encoding="utf-8")
            return {"downloaded_count": 1}
        return {"downloaded_count": 0}

    monkeypatch.setattr(cli_main, "download_s3_prefix_to_local_dir", _fake_download_prefix)

    restored = cli_main._restore_cloud_weights_config(
        workspace_dir=workspace,
        settings=settings,
        process_scope="p2p",
    )

    assert restored == workspace / "config" / "weights.yaml"
    assert restored is not None and restored.exists()
    assert "fallback_weight" in restored.read_text(encoding="utf-8")
    assert requested_uris[0] == "s3://bucket/artifacts/mappings/p2p/"


def test_rf14c11_ensure_report_dictionary_artifacts_creates_run_local_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_results" / "r1"
    run_dir.mkdir(parents=True, exist_ok=True)
    dd_json, dd_md = cli_main._ensure_report_dictionary_artifacts(run_dir=run_dir)
    assert dd_json.exists()
    assert dd_md.exists()
    json_text = dd_json.read_text(encoding="utf-8").strip()
    assert json_text.startswith("{") and json_text.endswith("}")
    assert "Data Dictionary" in dd_md.read_text(encoding="utf-8")


def test_rf14c11_cloud_graph_mode_runs_graph_after_deterministic(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    settings["pipeline_mode"] = "graph"
    settings["process_scope"] = "p2p"
    settings["process_family"] = "p2p"
    settings["process_family_explicit"] = True
    calls = {"graph": 0, "upload": 0, "state": 0}

    class _FakeTmpDir:
        def __init__(self, path: Path) -> None:
            self.name = str(path)

        def cleanup(self) -> None:
            return None

    monkeypatch.setattr(cli_main.tempfile, "TemporaryDirectory", lambda prefix: _FakeTmpDir(tmp_path / "ws_graph"))
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
    monkeypatch.setattr(cli_main, "compute_artifact_hash", lambda **kwargs: {"artifact_hash": "hash-graph"})
    monkeypatch.setattr(cli_main, "read_last_artifact_hash_state", lambda **kwargs: None)

    def _fake_execute_local(*, inner_args, resolved_settings):
        run_dir = Path.cwd() / "run_results" / "cloud-run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "schema_summary.json").write_text("{}", encoding="utf-8")
        (run_dir / "run_metadata.json").write_text('{"dataset_hash":"d1"}', encoding="utf-8")
        return 0

    def _fake_execute_graph(**kwargs):
        calls["graph"] += 1
        run_dir = Path.cwd() / "run_results" / "cloud-run-1" / "graph"
        run_dir.mkdir(parents=True, exist_ok=True)
        for name in ("graph_state.json", "hypotheses.json", "findings.json", "scores.json", "manifest.json"):
            (run_dir / name).write_text("{}", encoding="utf-8")
        (run_dir / "selected_tests.json").write_text("[]", encoding="utf-8")
        assert kwargs["settings"]["process_family"] == "p2p"
        return 0

    monkeypatch.setattr(cli_main, "_execute_local_pipeline_in_workspace", _fake_execute_local)
    monkeypatch.setattr(cli_main, "_execute_graph_pipeline_in_workspace", _fake_execute_graph)
    monkeypatch.setattr(
        cli_main,
        "upload_run_outputs",
        lambda **kwargs: calls.__setitem__("upload", calls["upload"] + 1),
    )
    monkeypatch.setattr(
        cli_main,
        "write_last_artifact_hash_state",
        lambda **kwargs: calls.__setitem__("state", calls["state"] + 1),
    )
    monkeypatch.setattr(cli_main, "_restore_cloud_red_flags_mapping", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_weights_config", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_catalog_dir", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_file_from_source_root", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_dir_from_source_root", lambda **kwargs: None)

    out = cli_main._run_pipeline_cloud(argparse.Namespace(process_family="p2p"), settings)
    assert out == 0
    assert calls["graph"] == 1
    assert calls["upload"] == 1
    assert calls["state"] == 1


def test_rf14c11_cloud_graph_mode_replays_selected_tests_after_graph(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    settings["pipeline_mode"] = "graph"
    settings["process_scope"] = "o2c"
    settings["process_family"] = "o2c"
    settings["process_family_explicit"] = True
    calls: list[dict[str, object]] = []

    class _FakeTmpDir:
        def __init__(self, path: Path) -> None:
            self.name = str(path)

        def cleanup(self) -> None:
            return None

    monkeypatch.setattr(cli_main.tempfile, "TemporaryDirectory", lambda prefix: _FakeTmpDir(tmp_path / "ws_graph_replay"))
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
    monkeypatch.setattr(cli_main, "compute_artifact_hash", lambda **kwargs: {"artifact_hash": "hash-graph"})
    monkeypatch.setattr(cli_main, "read_last_artifact_hash_state", lambda **kwargs: None)

    def _fake_execute_local(*, inner_args, resolved_settings):
        calls.append(
            {
                "pipeline_mode": resolved_settings.get("pipeline_mode"),
                "select_tests": list(resolved_settings.get("select_tests") or []),
            }
        )
        run_dir = Path.cwd() / "run_results" / "cloud-run-1"
        (run_dir / "graph").mkdir(parents=True, exist_ok=True)
        (run_dir / "schema_summary.json").write_text("{}", encoding="utf-8")
        (run_dir / "run_metadata.json").write_text('{"dataset_hash":"d1"}', encoding="utf-8")
        return 0

    def _fake_execute_graph(**kwargs):
        run_dir = Path.cwd() / "run_results" / "cloud-run-1" / "graph"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "selected_tests.json").write_text(
            json.dumps(
                [
                    {"test_id": "TST-O2C-DELIVERY-QUANTITY-MISMATCH"},
                    {"test_id": "TST-O2C-PRICE-OUTLIER"},
                ]
            ),
            encoding="utf-8",
        )
        for name in ("graph_state.json", "hypotheses.json", "findings.json", "scores.json", "manifest.json"):
            (run_dir / name).write_text("{}", encoding="utf-8")
        return 0

    monkeypatch.setattr(cli_main, "_execute_local_pipeline_in_workspace", _fake_execute_local)
    monkeypatch.setattr(cli_main, "_execute_graph_pipeline_in_workspace", _fake_execute_graph)
    monkeypatch.setattr(cli_main, "upload_run_outputs", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "write_last_artifact_hash_state", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_red_flags_mapping", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_weights_config", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_catalog_dir", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_file_from_source_root", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_dir_from_source_root", lambda **kwargs: None)

    out = cli_main._run_pipeline_cloud(argparse.Namespace(process_family="o2c"), settings)
    assert out == 0
    assert calls[0]["select_tests"] == []
    assert calls[1]["select_tests"] == [
        "TST-O2C-DELIVERY-QUANTITY-MISMATCH",
        "TST-O2C-PRICE-OUTLIER",
    ]


def test_rf14c11_cloud_graph_mode_rejects_both_scope(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    settings["pipeline_mode"] = "graph"
    settings["process_scope"] = "both"
    settings["process_family"] = "p2p"
    settings["process_family_explicit"] = True

    class _FakeTmpDir:
        def __init__(self, path: Path) -> None:
            self.name = str(path)

        def cleanup(self) -> None:
            return None

    monkeypatch.setattr(cli_main.tempfile, "TemporaryDirectory", lambda prefix: _FakeTmpDir(tmp_path / "ws_graph_both"))
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
    monkeypatch.setattr(cli_main, "compute_artifact_hash", lambda **kwargs: {"artifact_hash": "hash-graph"})
    monkeypatch.setattr(cli_main, "read_last_artifact_hash_state", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_execute_local_pipeline_in_workspace", lambda **kwargs: 0)
    monkeypatch.setattr(cli_main, "_restore_cloud_red_flags_mapping", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_weights_config", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_catalog_dir", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_file_from_source_root", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_dir_from_source_root", lambda **kwargs: None)

    out = cli_main._run_pipeline_cloud(argparse.Namespace(process_family="p2p"), settings)
    assert out == 2


def test_rf14c11_execute_graph_pipeline_invokes_run_graph_full(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path
    run_id = "r-graph"
    run_dir = workspace / "run_results" / run_id
    (run_dir / "graph").mkdir(parents=True, exist_ok=True)
    (run_dir / "schema_summary.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_metadata.json").write_text('{"dataset_hash":"d-hash"}', encoding="utf-8")
    for name in ("graph_state.json", "hypotheses.json", "selected_tests.json", "findings.json", "scores.json", "manifest.json"):
        (run_dir / "graph" / name).write_text("{}", encoding="utf-8")

    calls = {"run_graph_full": 0}

    def _fake_run_graph_full(*, run_id, dataset_hash="", input_zip="", run_metadata_overrides=None, execute_kb_index=True, sequence=None):
        calls["run_graph_full"] += 1
        assert run_id == "r-graph"
        assert dataset_hash == "d-hash"
        assert str(input_zip).endswith("erp_fraud_data.zip")
        assert execute_kb_index is False
        assert isinstance(run_metadata_overrides, dict)
        assert run_metadata_overrides.get("process_family") == "o2c"
        assert run_metadata_overrides.get("schema_name") == "o2c"
        assert run_metadata_overrides.get("table_name") == "o2c_order"
        assert Path(str(run_metadata_overrides.get("schema_summary_path", ""))).is_absolute()
        assert Path(str(run_metadata_overrides.get("db_path", ""))).is_absolute()
        assert Path(str(run_metadata_overrides.get("catalog_path", ""))).is_absolute()
        return object()

    monkeypatch.setattr(cli_main, "run_graph_full", _fake_run_graph_full)

    cwd = Path.cwd()
    try:
        import os

        os.chdir(workspace)
        settings = _base_settings()
        settings["process_family"] = "o2c"
        settings["schema_name"] = "main"
        settings["table_name"] = "fraud_1"
        settings["o2c_target_schema"] = "o2c"
        out = cli_main._execute_graph_pipeline_in_workspace(
            settings=settings,
            run_id=run_id,
            workspace_input_zip=workspace / "erp_fraud_data.zip",
            process_scope="o2c",
            artifact_hash="a1",
        )
    finally:
        os.chdir(cwd)
    assert out == 0
    assert calls["run_graph_full"] == 1
    graph_state_payload = json.loads((run_dir / "graph" / "graph_state.json").read_text(encoding="utf-8"))
    run_metadata_payload = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert graph_state_payload["run_metadata"]["incomplete_artifacts"] == ["second_level_analysis.json"]
    assert run_metadata_payload["incomplete_artifacts"] == ["second_level_analysis.json"]


def test_rf14c11_execute_graph_pipeline_propagates_llm_mode_real(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path
    run_id = "r-graph-real"
    run_dir = workspace / "run_results" / run_id
    (run_dir / "graph").mkdir(parents=True, exist_ok=True)
    (run_dir / "schema_summary.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_metadata.json").write_text('{"dataset_hash":"d-hash"}', encoding="utf-8")
    for name in ("graph_state.json", "hypotheses.json", "selected_tests.json", "findings.json", "scores.json", "manifest.json"):
        (run_dir / "graph" / name).write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_run_graph_full(*, run_id, dataset_hash="", input_zip="", run_metadata_overrides=None, execute_kb_index=True, sequence=None):
        assert run_id == "r-graph-real"
        assert dataset_hash == "d-hash"
        assert isinstance(run_metadata_overrides, dict)
        assert execute_kb_index is False
        captured.update(run_metadata_overrides)
        return object()

    monkeypatch.setattr(cli_main, "run_graph_full", _fake_run_graph_full)

    cwd = Path.cwd()
    try:
        import os

        os.chdir(workspace)
        settings = _base_settings()
        settings["process_family"] = "p2p"
        settings["llm_mode"] = "real"
        settings["kb_index_enabled"] = True
        settings["kb_index_explicit"] = False
        settings["kb_index_cli_explicit"] = False
        out = cli_main._execute_graph_pipeline_in_workspace(
            settings=settings,
            run_id=run_id,
            workspace_input_zip=workspace / "erp_fraud_data.zip",
            process_scope="p2p",
            artifact_hash="a1",
        )
    finally:
        os.chdir(cwd)
    assert out == 0
    assert captured.get("llm_mode") == "real"
    # Por defecto (si no se solicita explícitamente), cloud graph no reconstruye KB.
    assert captured.get("kb_index_enabled") is False
    # Pero sí mantiene búsqueda KB activa para contexto documental.
    assert captured.get("kb_search_enabled") is True


def test_rf14c11_execute_graph_pipeline_does_not_enable_kb_from_config_only(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path
    run_id = "r-graph-kb-cfg"
    run_dir = workspace / "run_results" / run_id
    (run_dir / "graph").mkdir(parents=True, exist_ok=True)
    (run_dir / "schema_summary.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_metadata.json").write_text('{"dataset_hash":"d-hash"}', encoding="utf-8")
    for name in ("graph_state.json", "hypotheses.json", "selected_tests.json", "findings.json", "scores.json", "manifest.json"):
        (run_dir / "graph" / name).write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_run_graph_full(*, run_id, dataset_hash="", input_zip="", run_metadata_overrides=None, execute_kb_index=True, sequence=None):
        assert isinstance(run_metadata_overrides, dict)
        assert execute_kb_index is False
        captured.update(run_metadata_overrides)
        return object()

    monkeypatch.setattr(cli_main, "run_graph_full", _fake_run_graph_full)

    cwd = Path.cwd()
    try:
        import os

        os.chdir(workspace)
        settings = _base_settings()
        # Simula "habilitado por config", sin flag CLI explícita:
        settings["kb_index_enabled"] = True
        settings["kb_index_explicit"] = True
        settings["kb_index_cli_explicit"] = False
        out = cli_main._execute_graph_pipeline_in_workspace(
            settings=settings,
            run_id=run_id,
            workspace_input_zip=workspace / "erp_fraud_data.zip",
            process_scope="p2p",
            artifact_hash="a1",
        )
    finally:
        os.chdir(cwd)
    assert out == 0
    assert captured.get("kb_index_enabled") is False
    assert captured.get("kb_search_enabled") is True


def test_rf14c11_execute_graph_pipeline_raises_on_aborted_graph(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path
    run_id = "r-graph-aborted"
    run_dir = workspace / "run_results" / run_id
    (run_dir / "graph").mkdir(parents=True, exist_ok=True)
    (run_dir / "schema_summary.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_metadata.json").write_text('{"dataset_hash":"d-hash"}', encoding="utf-8")
    for name in ("graph_state.json", "hypotheses.json", "selected_tests.json", "findings.json", "scores.json", "manifest.json"):
        (run_dir / "graph" / name).write_text("{}", encoding="utf-8")

    class _FakeState:
        def __init__(self) -> None:
            self.run_metadata = {"graph_status": "ABORTED", "graph_abort_reason": "precondition_failed_before_planning"}

    monkeypatch.setattr(cli_main, "run_graph_full", lambda **kwargs: _FakeState())

    cwd = Path.cwd()
    try:
        import os

        os.chdir(workspace)
        settings = _base_settings()
        settings["process_family"] = "p2p"
        try:
            cli_main._execute_graph_pipeline_in_workspace(
                settings=settings,
                run_id=run_id,
                workspace_input_zip=workspace / "erp_fraud_data.zip",
                process_scope="p2p",
                artifact_hash="a1",
            )
            assert False, "Expected RuntimeError for ABORTED graph"
        except RuntimeError as exc:
            assert "Grafo ABORTED" in str(exc)
    finally:
        os.chdir(cwd)


def test_rf14c11_execute_graph_pipeline_ignores_kb_abort_when_rebuild_not_requested(
    monkeypatch, tmp_path: Path
) -> None:
    workspace = tmp_path
    run_id = "r-graph-kb-abort"
    run_dir = workspace / "run_results" / run_id
    graph_dir = run_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "schema_summary.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_metadata.json").write_text('{"dataset_hash":"d-hash"}', encoding="utf-8")
    graph_state_path = graph_dir / "graph_state.json"
    graph_state_path.write_text(json.dumps({"run_metadata": {"graph_status": "ABORTED"}}), encoding="utf-8")
    for name in ("hypotheses.json", "selected_tests.json", "findings.json", "scores.json", "manifest.json"):
        (graph_dir / name).write_text("{}", encoding="utf-8")

    class _FakeState:
        def __init__(self) -> None:
            self.run_metadata = {"graph_status": "ABORTED", "graph_abort_reason": "node_failed:kb_index:ValueError"}

    monkeypatch.setattr(cli_main, "run_graph_full", lambda **kwargs: _FakeState())

    cwd = Path.cwd()
    try:
        import os

        os.chdir(workspace)
        settings = _base_settings()
        settings["kb_index_cli_explicit"] = False
        out = cli_main._execute_graph_pipeline_in_workspace(
            settings=settings,
            run_id=run_id,
            workspace_input_zip=workspace / "erp_fraud_data.zip",
            process_scope="p2p",
            artifact_hash="a1",
        )
    finally:
        os.chdir(cwd)

    assert out == 0
    payload = json.loads(graph_state_path.read_text(encoding="utf-8"))
    metadata = payload.get("run_metadata", {})
    assert metadata.get("graph_status") == "OK_WITH_WARNINGS"
    assert metadata.get("graph_warning") == "kb_index_failed_but_rebuild_not_requested"
    assert metadata.get("kb_index_status") == "SKIPPED_NO_REBUILD"


def test_rf14c11_cloud_restore_catalog_for_scope(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    workspace = tmp_path / "ws_catalog"
    workspace.mkdir(parents=True, exist_ok=True)
    requested_uris: list[str] = []

    def _fake_download_prefix(*, s3_uri, local_dir):
        requested_uris.append(str(s3_uri))
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        if str(s3_uri).endswith("/artifacts/catalogs/p2p/"):
            (path / "tst_sample.yaml").write_text("id: TST-SAMPLE\nversion: 1.0.0\n", encoding="utf-8")
            return {"downloaded_count": 1}
        return {"downloaded_count": 0}

    monkeypatch.setattr(cli_main, "download_s3_prefix_to_local_dir", _fake_download_prefix)
    restored = cli_main._restore_cloud_catalog_dir(
        workspace_dir=workspace,
        settings=settings,
        process_family="p2p",
        target_relative_path="tests/catalog",
    )
    assert restored == workspace / "tests" / "catalog"
    assert restored is not None and (restored / "tst_sample.yaml").exists()
    assert requested_uris[0] == "s3://bucket/artifacts/catalogs/p2p/"


def test_rf14c11_materialize_workspace_file_from_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "srcroot"
    workspace = tmp_path / "ws_cfg"
    (source_root / "config").mkdir(parents=True, exist_ok=True)
    (source_root / "config" / "canonical_schema_o2c.yaml").write_text("entities: []\n", encoding="utf-8")

    restored = cli_main._materialize_workspace_file_from_source_root(
        workspace_dir=workspace,
        source_root=source_root,
        relative_path="config/canonical_schema_o2c.yaml",
        log_label="o2c_canonical_schema_config",
    )
    assert restored == workspace / "config" / "canonical_schema_o2c.yaml"
    assert restored is not None and restored.exists()


def test_rf14c11_materialize_workspace_glob_from_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "srcroot"
    workspace = tmp_path / "ws_glob"
    (source_root / "docs").mkdir(parents=True, exist_ok=True)
    (source_root / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
    (source_root / "docs" / "b.md").write_text("# B\n", encoding="utf-8")

    restored = cli_main._materialize_workspace_glob_from_source_root(
        workspace_dir=workspace,
        source_root=source_root,
        glob_pattern="docs/*.md",
        log_label="kb_docs",
    )
    assert restored == 2
    assert (workspace / "docs" / "a.md").exists()
    assert (workspace / "docs" / "b.md").exists()


def test_rf14c11_materialize_cloud_kb_sources_from_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "srcroot"
    workspace = tmp_path / "ws_kb"
    (source_root / "config").mkdir(parents=True, exist_ok=True)
    (source_root / "docs" / "external").mkdir(parents=True, exist_ok=True)
    (source_root / "docs").mkdir(parents=True, exist_ok=True)
    (source_root / "tests" / "catalog").mkdir(parents=True, exist_ok=True)
    (source_root / "docs" / "external" / "ref.pdf").write_bytes(b"pdf")
    (source_root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (source_root / "data_dictionary.json").write_text('{"fields":[]}', encoding="utf-8")
    (source_root / "tests" / "catalog" / "tst_sample.yaml").write_text("id: T1\n", encoding="utf-8")
    kb_cfg = source_root / "config" / "kb_sources.yaml"
    kb_cfg.write_text(
        "\n".join(
            [
                "version: 1.0.0",
                "sources:",
                "  - source_id: ref_pdf",
                "    enabled: true",
                "    required: true",
                "    type: file",
                "    path: docs/external/ref.pdf",
                "  - source_id: docs_md",
                "    enabled: true",
                "    required: true",
                "    type: glob",
                "    path: docs/*.md",
                "  - source_id: dictionary_json",
                "    enabled: true",
                "    required: true",
                "    type: file",
                "    path: data_dictionary.json",
                "  - source_id: catalog_yaml",
                "    enabled: true",
                "    required: true",
                "    type: glob",
                "    path: tests/catalog/*.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )

    restored = cli_main._materialize_cloud_kb_sources_from_source_root(
        workspace_dir=workspace,
        source_root=source_root,
        kb_sources_config_path=str(kb_cfg),
    )
    assert restored == 4
    assert (workspace / "docs" / "external" / "ref.pdf").exists()
    assert (workspace / "docs" / "guide.md").exists()
    assert (workspace / "data_dictionary.json").exists()
    assert (workspace / "tests" / "catalog" / "tst_sample.yaml").exists()


def test_rf14c11_cloud_flow_materializes_kb_sources_when_rebuild_requested(monkeypatch, tmp_path: Path) -> None:
    settings = _base_settings()
    settings["kb_index_enabled"] = True
    settings["kb_index_cli_explicit"] = True
    calls = {"kb_sources": 0}

    class _FakeTmpDir:
        def __init__(self, path: Path) -> None:
            self.name = str(path)

        def cleanup(self) -> None:
            return None

    monkeypatch.setattr(cli_main.tempfile, "TemporaryDirectory", lambda prefix: _FakeTmpDir(tmp_path / "ws_kb_rebuild"))
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
    monkeypatch.setattr(cli_main, "compute_artifact_hash", lambda **kwargs: {"artifact_hash": "ahash-kb"})
    monkeypatch.setattr(cli_main, "read_last_artifact_hash_state", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_execute_local_pipeline_in_workspace", lambda **kwargs: 0)
    monkeypatch.setattr(cli_main, "_execute_graph_pipeline_in_workspace", lambda **kwargs: 0)
    monkeypatch.setattr(cli_main, "upload_run_outputs", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "write_last_artifact_hash_state", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_red_flags_mapping", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_weights_config", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_restore_cloud_catalog_dir", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_file_from_source_root", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "_materialize_workspace_dir_from_source_root", lambda **kwargs: None)

    def _fake_materialize_kb_sources(**kwargs):
        calls["kb_sources"] += 1
        return 3

    monkeypatch.setattr(cli_main, "_materialize_cloud_kb_sources_from_source_root", _fake_materialize_kb_sources)

    out = cli_main._run_pipeline_cloud(argparse.Namespace(process_family="p2p"), settings)
    assert out == 0
    assert calls["kb_sources"] == 1
