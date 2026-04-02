from __future__ import annotations

import json
from pathlib import Path

from scripts.check_real_cloud_readiness import evaluate_runs


def _write_graph_state(run_dir: Path, run_metadata: dict) -> None:
    path = run_dir / "graph" / "graph_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_metadata": run_metadata}, ensure_ascii=False), encoding="utf-8")


def test_cloud_readiness_passes_with_three_valid_real_runs(tmp_path: Path) -> None:
    for idx in range(1, 4):
        run_id = f"run-{idx}"
        _write_graph_state(
            tmp_path / run_id,
            {
                "graph_status": "OK",
                "llm_mode": "real",
                "langsmith_tags": ["llm_mode:real"],
                "llm_runtime_by_node": {
                    "hypothesis_planner": {
                        "status": "OK",
                        "fallback_used": False,
                        "total_tokens": 100,
                        "latency_ms": 1200,
                    },
                    "test_planner": {
                        "status": "OK",
                        "fallback_used": False,
                        "total_tokens": 50,
                        "latency_ms": 600,
                    },
                    "expert_explainer": {
                        "status": "OK",
                        "fallback_used": False,
                        "total_tokens": 200,
                        "latency_ms": 2400,
                    },
                    "scoring": {
                        "status": "OK",
                        "fallback_used": False,
                        "total_tokens": 60,
                        "latency_ms": 900,
                    },
                },
            },
        )
    payload = evaluate_runs(base_dir=tmp_path, run_ids=["run-1", "run-2", "run-3"])
    assert payload["cloud_ready"] is True
    assert payload["passed_runs"] == 3


def test_cloud_readiness_fails_when_a_run_uses_fallback(tmp_path: Path) -> None:
    for idx in range(1, 4):
        run_id = f"run-{idx}"
        scoring_fallback = idx == 2
        _write_graph_state(
            tmp_path / run_id,
            {
                "graph_status": "OK",
                "llm_mode": "real",
                "langsmith_tags": ["llm_mode:real"],
                "llm_runtime_by_node": {
                    "hypothesis_planner": {"status": "OK", "fallback_used": False, "total_tokens": 100, "latency_ms": 1},
                    "test_planner": {"status": "OK", "fallback_used": False, "total_tokens": 100, "latency_ms": 1},
                    "expert_explainer": {"status": "OK", "fallback_used": False, "total_tokens": 100, "latency_ms": 1},
                    "scoring": {
                        "status": "OK",
                        "fallback_used": scoring_fallback,
                        "total_tokens": 100,
                        "latency_ms": 1,
                    },
                },
            },
        )
    payload = evaluate_runs(base_dir=tmp_path, run_ids=["run-1", "run-2", "run-3"])
    assert payload["cloud_ready"] is False
    failed = [row for row in payload["checks"] if not row["passed"]]
    assert failed and "fallback_used" in "\n".join(failed[0]["errors"])
