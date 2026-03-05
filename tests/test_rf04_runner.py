from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.erp_fraud.catalog.test_runner import TestRunner as CatalogRunner


def _ok_result(test_id: str, *, duration_ms: int = 1) -> dict:
    return {
        "result_schema_version": "1.0.0",
        "generated_at_utc": "2026-03-05T00:00:00+00:00",
        "test_id": test_id,
        "test_version": "1.0.0",
        "fraud_type": "test",
        "status": "OK",
        "finding_count": 0,
        "duration_ms": duration_ms,
        "runner_duration_ms": duration_ms,
        "columns": [],
        "rows": [],
        "metadata": {
            "implementation_type": "sql",
            "executed_on": "main.fraud_1",
        },
    }


def test_run_all_allowlist_rejects_unknown_id() -> None:
    runner = CatalogRunner(db_path="erp.duckdb")
    with pytest.raises(ValueError, match="lista blanca"):
        runner.run_all(
            ["TST-NO-EXISTE"],
            catalog_path="tests/catalog",
            validate_schema=True,
        )


def test_run_all_captures_error_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CatalogRunner(db_path="erp.duckdb")

    def fake_run(spec: dict) -> dict:
        test_id = str(spec.get("id"))
        if test_id == "TST-DUPLICATE-POSTINGS":
            raise RuntimeError("fallo intencional")
        return _ok_result(test_id, duration_ms=5)

    monkeypatch.setattr(runner, "run", fake_run)

    out = runner.run_all(
        ["TST-DUPLICATE-POSTINGS", "TST-UNUSUAL-AMOUNT-BY-VENDOR"],
        catalog_path="tests/catalog",
        validate_schema=True,
    )

    assert len(out) == 2
    assert out[0]["status"] == "ERROR"
    assert "error_summary" in out[0]
    assert out[1]["status"] == "OK"


def test_run_all_timeout_marks_timeout() -> None:
    class SlowRunner(CatalogRunner):
        def run(self, test_spec: dict) -> dict:
            time.sleep(0.12)
            return _ok_result(str(test_spec.get("id")), duration_ms=120)

    runner = SlowRunner(db_path="erp.duckdb")
    out = runner.run_all(
        ["TST-DUPLICATE-POSTINGS", "TST-UNUSUAL-AMOUNT-BY-VENDOR"],
        catalog_path="tests/catalog",
        validate_schema=True,
        timeout_ms=20,
    )

    assert [item["status"] for item in out] == ["TIMEOUT", "TIMEOUT"]
    assert all("error_summary" in item for item in out)


def test_run_all_stores_phase_and_test_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CatalogRunner(db_path="erp.duckdb")
    monkeypatch.setattr(runner, "run", lambda spec: _ok_result(str(spec.get("id")), duration_ms=7))

    _ = runner.run_all(
        ["TST-DUPLICATE-POSTINGS"],
        catalog_path="tests/catalog",
        validate_schema=True,
    )
    metrics = runner.get_last_run_metrics()

    assert metrics["tests_count"] == 1
    assert sorted(metrics["phase_duration_ms"].keys()) == ["execution", "selection", "total"]
    assert metrics["tests_duration_ms"][0]["test_id"] == "TST-DUPLICATE-POSTINGS"


def test_write_test_runs_json_persists_required_fields(tmp_path: Path) -> None:
    runner = CatalogRunner(db_path="erp.duckdb")
    results = [
        _ok_result("TST-DUPLICATE-POSTINGS", duration_ms=11),
        {
            **_ok_result("TST-UNUSUAL-AMOUNT-BY-VENDOR", duration_ms=9),
            "status": "ERROR",
            "error_summary": "RuntimeError: boom",
        },
    ]

    out_path = runner.write_test_runs_json(
        output_path=tmp_path / "test_runs.json",
        run_id="rf04-06-unit",
        results=results,
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert len(payload["test_runs"]) == 2
    assert sorted(payload["test_runs"][0].keys()) == [
        "duration_ms",
        "error_summary",
        "status",
        "test_id",
        "version",
    ]


def test_run_all_writes_test_logs_jsonl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CatalogRunner(db_path="erp.duckdb")
    monkeypatch.setattr(runner, "run", lambda spec: _ok_result(str(spec.get("id")), duration_ms=3))

    log_path = tmp_path / "test_runner_logs.jsonl"
    _ = runner.run_all(
        ["TST-DUPLICATE-POSTINGS", "TST-UNUSUAL-AMOUNT-BY-VENDOR"],
        catalog_path="tests/catalog",
        validate_schema=True,
        run_id="rf04-07-unit",
        log_path=log_path,
    )

    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [line["event"] for line in lines] == ["test_start", "test_end", "test_start", "test_end"]
    assert all("run_id" in line and "test_id" in line for line in lines)
