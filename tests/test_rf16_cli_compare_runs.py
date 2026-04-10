from __future__ import annotations

import json
from pathlib import Path

from src.erp_fraud.cli.main import main


def _write_run_fixture(
    *,
    base_dir: Path,
    run_id: str,
    process_family: str,
    selected_tests: list[str],
    findings: list[dict[str, object]],
) -> None:
    run_dir = base_dir / run_id
    graph_dir = run_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    (graph_dir / "selected_tests.json").write_text(
        json.dumps([{"hypothesis_id": "HYP-001", "test_id": test_id} for test_id in selected_tests], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (graph_dir / "findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    (graph_dir / "hypotheses.json").write_text(
        json.dumps([{"hypothesis_id": "HYP-001", "fraud_type": "amount_anomaly"}], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (graph_dir / "scores.json").write_text(
        json.dumps([{"final_label": "amount_anomaly", "confidence": 0.9}], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (graph_dir / "graph_state.json").write_text(
        json.dumps(
            {
                "run_metadata": {
                    "process_family": process_family,
                    "llm_mode": "real",
                    "graph_status": "OK",
                    "updated_at_utc": "2026-04-10T12:00:00+00:00",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.json").write_text(
        json.dumps({"summary": {"overall_status": "OK", "findings_total": sum(int(x.get("finding_count", 0) or 0) for x in findings)}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_rf16_cli_list_runs_and_compare(tmp_path: Path, capsys: object) -> None:
    base_dir = tmp_path / "run_results"
    _write_run_fixture(
        base_dir=base_dir,
        run_id="p2p-a",
        process_family="p2p",
        selected_tests=["TST-UNUSUAL-AMOUNT-BY-VENDOR"],
        findings=[{"test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR", "fraud_type": "amount_anomaly", "finding_count": 2}],
    )
    _write_run_fixture(
        base_dir=base_dir,
        run_id="o2c-b",
        process_family="o2c",
        selected_tests=["TST-O2C-DELIVERY-QUANTITY-MISMATCH"],
        findings=[
            {"test_id": "TST-O2C-DELIVERY-QUANTITY-MISMATCH", "fraud_type": "delivery_manipulation", "finding_count": 1}
        ],
    )

    rc = main(["list-runs", "--base-dir", str(base_dir), "--output-json"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert int(payload.get("count", 0)) >= 2

    rc = main(
        [
            "compare-runs",
            "p2p-a",
            "o2c-b",
            "--base-dir",
            str(base_dir),
            "--analysis-id",
            "rf16-it",
        ]
    )
    assert rc == 0

    analysis_dir = base_dir / "rf16-it"
    json_path = analysis_dir / "rf16_second_level_analysis.json"
    md_path = analysis_dir / "rf16_second_level_analysis.md"
    assert json_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload.get("runs_count") == 2
    assert payload.get("process_families") == {"o2c": 1, "p2p": 1}
