from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.erp_fraud.storage.run_outputs import RunOutputValidationError, validate_required_run_outputs


def _write(path: Path, content: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_base_required(run_dir: Path) -> None:
    _write(
        run_dir / "run_metadata.json",
        json.dumps(
            {"run_id": "r1", "process_scope": "p2p", "artifact_hash": "abc"},
            ensure_ascii=False,
        ),
    )
    _write(run_dir / "schema_summary.json", "{}")
    _write(run_dir / "report.json", "{}")
    _write(run_dir / "ranking.json", "[]")


def test_rf14c12_complete_ok(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-ok"
    _write_base_required(run_dir)
    out = validate_required_run_outputs(run_dir=run_dir)
    assert out["ok"] is True
    assert out["missing_required"] == []


def test_rf14c12_accepts_process_scope_both_in_run_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-both"
    _write(
        run_dir / "run_metadata.json",
        json.dumps(
            {"run_id": "r-both", "process_scope": "both", "artifact_hash": "abc-both"},
            ensure_ascii=False,
        ),
    )
    _write(run_dir / "schema_summary.json", "{}")
    _write(run_dir / "report.json", "{}")
    _write(run_dir / "ranking.json", "[]")
    out = validate_required_run_outputs(run_dir=run_dir)
    assert out["ok"] is True


def test_rf14c12_missing_required_fails(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-missing"
    _write_base_required(run_dir)
    (run_dir / "ranking.json").unlink()
    with pytest.raises(RunOutputValidationError, match="Faltan outputs obligatorios"):
        validate_required_run_outputs(run_dir=run_dir)


def test_rf14c12_missing_optional_graph_outputs_does_not_fail(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-graph"
    _write_base_required(run_dir)
    _write(run_dir / "graph" / "graph_state.json", "{}")
    _write(run_dir / "graph" / "hypotheses.json", "[]")
    _write(run_dir / "graph" / "selected_tests.json", "[]")
    _write(run_dir / "graph" / "findings.json", "[]")
    _write(run_dir / "graph" / "scores.json", "[]")
    out = validate_required_run_outputs(run_dir=run_dir, graph_active=True)
    assert out["ok"] is True
    assert "graph/explanations.json" in out["missing_optional"]


def test_rf14c12_run_metadata_minimum_content_required(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-meta-bad"
    _write(run_dir / "run_metadata.json", json.dumps({"run_id": "r1"}, ensure_ascii=False))
    _write(run_dir / "schema_summary.json", "{}")
    _write(run_dir / "report.json", "{}")
    _write(run_dir / "ranking.json", "[]")
    with pytest.raises(RunOutputValidationError, match="process_scope"):
        validate_required_run_outputs(run_dir=run_dir)
