from __future__ import annotations

import json
import os
from pathlib import Path

from src.erp_fraud.storage.runs_comparison import (
    compare_runs,
    load_run_snapshot,
    pick_latest_run_ids_by_process_family,
)


def _write_run_fixture(
    *,
    base_dir: Path,
    run_id: str,
    process_family: str,
    selected_tests: list[str],
    findings: list[dict[str, object]],
    final_label: str,
    confidence: float,
) -> None:
    run_dir = base_dir / run_id
    graph_dir = run_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    (graph_dir / "selected_tests.json").write_text(
        json.dumps(
            [{"hypothesis_id": "HYP-001", "test_id": test_id, "source": "planner_llm"} for test_id in selected_tests],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (graph_dir / "findings.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (graph_dir / "hypotheses.json").write_text(
        json.dumps(
            [
                {
                    "hypothesis_id": "HYP-001",
                    "fraud_type": "amount_anomaly",
                    "candidate_test_ids": selected_tests,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (graph_dir / "scores.json").write_text(
        json.dumps(
            [
                {
                    "final_label": final_label,
                    "confidence": confidence,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (graph_dir / "graph_state.json").write_text(
        json.dumps(
            {
                "run_metadata": {
                    "process_family": process_family,
                    "llm_mode": "real",
                    "graph_status": "OK",
                    "langsmith_trace_link": f"https://smith.langchain.com/r/{run_id}",
                    "updated_at_utc": "2026-04-10T12:00:00+00:00",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.json").write_text(
        json.dumps(
            {"summary": {"overall_status": "OK", "findings_total": sum(int(r.get("finding_count", 0) or 0) for r in findings)}},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_rf16_load_snapshot_and_compare_cross_process(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    _write_run_fixture(
        base_dir=base_dir,
        run_id="p2p-run-01",
        process_family="p2p",
        selected_tests=["TST-UNUSUAL-AMOUNT-BY-VENDOR", "TST-JUST-BELOW-AUTH-THRESHOLD"],
        findings=[
            {"test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR", "fraud_type": "amount_anomaly", "finding_count": 6},
            {"test_id": "TST-JUST-BELOW-AUTH-THRESHOLD", "fraud_type": "authorization_bypass", "finding_count": 4},
        ],
        final_label="amount_anomaly",
        confidence=0.91,
    )
    _write_run_fixture(
        base_dir=base_dir,
        run_id="o2c-run-01",
        process_family="o2c",
        selected_tests=["TST-O2C-DELIVERY-QUANTITY-MISMATCH"],
        findings=[
            {"test_id": "TST-O2C-DELIVERY-QUANTITY-MISMATCH", "fraud_type": "delivery_manipulation", "finding_count": 3},
        ],
        final_label="delivery_manipulation",
        confidence=0.88,
    )

    snap = load_run_snapshot(run_id="p2p-run-01", base_dir=base_dir)
    assert snap.run_id == "p2p-run-01"
    assert snap.process_family == "p2p"
    assert snap.selected_tests_count == 2
    assert snap.findings_total == 10
    assert snap.final_label == "amount_anomaly"

    payload = compare_runs(run_ids=["p2p-run-01", "o2c-run-01"], base_dir=base_dir)
    assert payload["rf_task"] == "RF16"
    assert payload["runs_count"] == 2
    assert payload["process_families"] == {"o2c": 1, "p2p": 1}
    assert isinstance(payload["recommendations"], list) and payload["recommendations"]
    sections = payload["comparison_sections"]
    assert [item["section"] for item in sections] == ["intra_run", "historical", "cross_process"]
    assert sections[2]["status"] == "comparison"
    assert "otra familia de proceso" in sections[2]["summary"]


def test_rf16_pick_latest_run_ids_by_family(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    _write_run_fixture(
        base_dir=base_dir,
        run_id="p2p-old",
        process_family="p2p",
        selected_tests=["TST-UNUSUAL-AMOUNT-BY-VENDOR"],
        findings=[{"test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR", "fraud_type": "amount_anomaly", "finding_count": 1}],
        final_label="amount_anomaly",
        confidence=0.8,
    )
    _write_run_fixture(
        base_dir=base_dir,
        run_id="o2c-new",
        process_family="o2c",
        selected_tests=["TST-O2C-DELIVERY-QUANTITY-MISMATCH"],
        findings=[
            {"test_id": "TST-O2C-DELIVERY-QUANTITY-MISMATCH", "fraud_type": "delivery_manipulation", "finding_count": 2}
        ],
        final_label="delivery_manipulation",
        confidence=0.85,
    )
    _write_run_fixture(
        base_dir=base_dir,
        run_id="p2p-new",
        process_family="p2p",
        selected_tests=["TST-JUST-BELOW-AUTH-THRESHOLD"],
        findings=[
            {"test_id": "TST-JUST-BELOW-AUTH-THRESHOLD", "fraud_type": "authorization_bypass", "finding_count": 1}
        ],
        final_label="authorization_bypass",
        confidence=0.7,
    )

    # Fuerza orden temporal distinto
    os.utime(base_dir / "p2p-old", (1000, 1000))
    os.utime(base_dir / "o2c-new", (2000, 2000))
    os.utime(base_dir / "p2p-new", (3000, 3000))

    picked = pick_latest_run_ids_by_process_family(base_dir=base_dir)
    assert sorted(picked) == ["o2c-new", "p2p-new"]


def test_rf16_pick_latest_reads_process_family_from_run_metadata_when_graph_missing(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    p2p_dir = base_dir / "p2p-cli-only"
    o2c_dir = base_dir / "o2c-cli-only"
    p2p_dir.mkdir(parents=True, exist_ok=True)
    o2c_dir.mkdir(parents=True, exist_ok=True)

    (p2p_dir / "run_metadata.json").write_text(
        json.dumps({"run_id": "p2p-cli-only", "process_family": "p2p", "llm_mode": "stub"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (o2c_dir / "run_metadata.json").write_text(
        json.dumps({"run_id": "o2c-cli-only", "process_family": "o2c", "llm_mode": "stub"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (p2p_dir / "report.json").write_text(
        json.dumps({"summary": {"overall_status": "OK"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (o2c_dir / "report.json").write_text(
        json.dumps({"summary": {"overall_status": "OK"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    os.utime(p2p_dir, (1000, 1000))
    os.utime(o2c_dir, (2000, 2000))

    picked = pick_latest_run_ids_by_process_family(base_dir=base_dir)
    assert sorted(picked) == ["o2c-cli-only", "p2p-cli-only"]
