from __future__ import annotations

import argparse
from pathlib import Path

from src.erp_fraud.cli.main import _build_run_paths, _resolve_run_settings, build_parser


def test_rf15e09_run_settings_include_kb_defaults() -> None:
    args = argparse.Namespace(
        input_zip=None,
        run_id=None,
        out_dir=None,
        db_path=None,
        schema_name=None,
        table_name=None,
        catalog=None,
        weights_config=None,
        timeout_ms=None,
        sample_top_n=None,
        top_k=None,
        select_tests=None,
        config=None,
        kb_index_enabled=None,
        kb_sources_config=None,
        kb_chunking_config=None,
        kb_chroma_config=None,
        process_family=None,
        o2c_canonical_schema_config=None,
        o2c_identity_config=None,
        o2c_mapping_config=None,
        o2c_target_schema=None,
    )
    settings = _resolve_run_settings(args)
    assert settings["kb_index_enabled"] is False
    assert settings["kb_sources_config"] == "config/kb_sources.yaml"
    assert settings["kb_chunking_config"] == "config/kb_chunking.yaml"
    assert settings["kb_chroma_config"] == "config/kb_chroma.yaml"
    assert settings["process_family"] == "p2p"
    assert settings["o2c_mapping_config"] == "config/column_mapping_o2c.yaml"


def test_rf15e09_build_run_paths_include_kb_artifacts(tmp_path: Path) -> None:
    paths = _build_run_paths(tmp_path / "run-001")
    assert "kb_index_manifest" in paths
    assert "kb_index_state" in paths
    assert paths["kb_index_manifest"].name == "kb_index_manifest.json"
    assert paths["kb_index_state"].name == "kb_index_state.json"


def test_rf15e09_cli_flag_no_kb_index_overrides_default() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "--input-zip", "erp_fraud_data.zip", "--no-kb-index"])
    settings = _resolve_run_settings(args)
    assert settings["kb_index_enabled"] is False


def test_rf15e09_cli_flag_kb_index_enabled_turns_on_rebuild() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "--input-zip", "erp_fraud_data.zip", "--kb-index-enabled"])
    settings = _resolve_run_settings(args)
    assert settings["kb_index_enabled"] is True
