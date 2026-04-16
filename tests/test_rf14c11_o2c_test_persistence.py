from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.erp_fraud.cli import main as cli_main


def _o2c_settings(tmp_path: Path) -> dict:
    return {
        "input_zip": str(tmp_path / "erp_fraud_data.zip"),
        "run_id": "o2c-persist-1",
        "out_dir": "run_results",
        "db_path": str(tmp_path / "erp.duckdb"),
        "schema_name": "main",
        "table_name": "fraud_1",
        "catalog": "tests/catalog_o2c",
        "weights_config": "config/weights.yaml",
        "timeout_ms": None,
        "sample_top_n": 20,
        "top_k": None,
        "select_tests": None,
        "select_fraud_types": None,
        "select_tags": None,
        "kb_index_enabled": False,
        "kb_index_cli_explicit": False,
        "kb_sources_config": "config/kb_sources.yaml",
        "kb_chunking_config": "config/kb_chunking.yaml",
        "kb_chroma_config": "config/kb_chroma.yaml",
        "llm_mode": "stub",
        "pipeline_mode": "deterministic",
        "process_family": "o2c",
        "process_family_explicit": True,
        "o2c_canonical_schema_config": "config/canonical_schema_o2c.yaml",
        "o2c_identity_config": "config/o2c_entity_identity.yaml",
        "o2c_mapping_config": "config/column_mapping_o2c.yaml",
        "o2c_target_schema": "o2c",
        "aws_region": "eu-west-1",
        "run_mode": "local",
        "s3_input_uri": "s3://bucket/inputs/",
        "s3_output_uri": "s3://bucket/runs/",
        "s3_state_uri": "s3://bucket/state/",
        "process_scope": "o2c",
    }


def test_rf14c11_o2c_pipeline_persists_test_run_artifacts(monkeypatch, tmp_path: Path) -> None:
    settings = _o2c_settings(tmp_path)
    Path(settings["input_zip"]).write_bytes(b"zip")

    monkeypatch.setattr(cli_main, "_resolve_run_settings", lambda _args: settings)
    class _FakeConn:
        def close(self) -> None:
            return None

    monkeypatch.setattr(cli_main, "get_duckdb_connection", lambda _db_path: _FakeConn())
    monkeypatch.setattr(cli_main, "_load_o2c_raw_tables_from_zip_if_needed", lambda **kwargs: {"loaded_tables": ["o2c_order"]})
    monkeypatch.setattr(cli_main, "_ensure_o2c_optional_placeholders", lambda _conn: [])
    monkeypatch.setattr(cli_main, "transform_raw_to_o2c_canonical", lambda **kwargs: {"entities_ok": 1})

    def _fake_write_o2c_validation_report_json(output_path, **kwargs):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"summary": {"overall_status": "OK"}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    monkeypatch.setattr(cli_main, "write_o2c_validation_report_json", _fake_write_o2c_validation_report_json)

    def _fake_write_schema_summary_json(output_path, **kwargs):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return path

    monkeypatch.setattr(cli_main, "write_schema_summary_json", _fake_write_schema_summary_json)
    monkeypatch.setattr(
        cli_main,
        "load_test_specs_from_catalog",
        lambda *args, **kwargs: [
            {
                "id": "TST-O2C-PRICE-OUTLIER",
                "name": "Price outlier",
                "fraud_type": "pricing_anomaly",
                "red_flag_id": "RF-O2C-001",
                "process_step": "order_pricing",
                "description": "Detects pricing outliers",
                "source": {"reference": "x"},
                "data_requirements": {"required_tables": ["o2c_order"]},
                "expected_output": {"finding_fields": ["sales_order_id"]},
                "evidence_columns": ["sales_order_id", "net_amount"],
                "logic": {"implementation_type": "sql", "sql_ref": "sql/tests/tst_o2c_price_outlier.sql"},
            }
        ],
    )

    def _fake_run_all_from_catalog(self, *, catalog_path, validate_schema, timeout_ms, run_id, log_path):
        Path(log_path).write_text(
            json.dumps({"run_id": run_id, "test_id": "TST-O2C-PRICE-OUTLIER", "status": "OK"}) + "\n",
            encoding="utf-8",
        )
        return [
            {
                "test_id": "TST-O2C-PRICE-OUTLIER",
                "test_version": "1.0.0",
                "fraud_type": "pricing_anomaly",
                "status": "OK",
                "finding_count": 1,
                "duration_ms": 10,
                "columns": ["sales_order_id", "net_amount"],
                "rows": [
                    {
                        "sales_order_id": "5000000001",
                        "net_amount": 999.0,
                        "keys": {"sales_order_id": "5000000001"},
                        "entity_key": "sales_order_id=5000000001",
                        "evidence_columns": ["sales_order_id", "net_amount"],
                        "metrics": {"net_amount": 999.0},
                        "drilldown_template": {"query_id": "drilldown_o2c_price_outlier_v1"},
                    }
                ],
                "metadata": {"implementation_type": "sql_ref", "executed_on": "o2c.o2c_order"},
            }
        ]

    monkeypatch.setattr(cli_main.TestRunner, "run_all_from_catalog", _fake_run_all_from_catalog)
    monkeypatch.setattr(cli_main.TestRunner, "run_all", _fake_run_all_from_catalog)
    monkeypatch.setattr(cli_main, "load_weights_config", lambda _path: {})
    monkeypatch.setattr(cli_main, "resolve_ranking_top_k", lambda **kwargs: 20)
    monkeypatch.setattr(cli_main, "aggregate_findings_by_entity", lambda **kwargs: [])

    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        out = cli_main._run_pipeline_local(argparse.Namespace(), resolved_settings=settings)
    finally:
        os.chdir(cwd)

    assert out == 0
    run_dir = tmp_path / "run_results" / settings["run_id"]
    assert (run_dir / "test_runner_logs.jsonl").exists()
    assert (run_dir / "test_runs.json").exists()
    assert (run_dir / "tests_outputs" / "TST-O2C-PRICE-OUTLIER" / "findings.jsonl").exists()
    assert (run_dir / "tests_outputs" / "TST-O2C-PRICE-OUTLIER" / "sample_top20.json").exists()

    report_payload = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report_payload["summary"]["tests_total"] == 1
    assert report_payload["summary"]["tests_ok"] == 1
