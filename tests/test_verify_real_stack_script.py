from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_real_stack import evaluate_runs


def _write_graph_state(tmp_path: Path, run_id: str, run_metadata: dict) -> None:
    path = tmp_path / run_id / "graph" / "graph_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": run_id, "run_metadata": run_metadata}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_verify_real_stack_passes_with_valid_real_run(tmp_path: Path) -> None:
    run_id = "real-ok"
    _write_graph_state(
        tmp_path,
        run_id,
        {
            "graph_status": "OK",
            "llm_mode": "real",
            "langsmith_trace_link": "https://eu.smith.langchain.com/o/p/projects/p/p/r/1",
            "langsmith_runs": {"status": "OK", "runs_published": 1, "trace_link": "https://x"},
            "llm_runtime_by_node": {
                "hypothesis_planner": {
                    "status": "OK",
                    "fallback_used": False,
                    "total_tokens": 10,
                    "latency_ms": 100,
                },
                "test_planner": {
                    "status": "OK",
                    "fallback_used": False,
                    "total_tokens": 10,
                    "latency_ms": 100,
                },
                "expert_explainer": {
                    "status": "OK",
                    "fallback_used": False,
                    "total_tokens": 10,
                    "latency_ms": 100,
                },
                "scoring": {
                    "status": "OK",
                    "fallback_used": False,
                    "total_tokens": 10,
                    "latency_ms": 100,
                },
            },
        },
    )
    out = evaluate_runs(
        base_dir=tmp_path,
        run_ids=[run_id],
        required_nodes=("hypothesis_planner", "test_planner", "expert_explainer", "scoring"),
        require_trace_link=True,
    )
    assert out["overall_ok"] is True
    assert out["passed_runs"] == 1


def test_verify_real_stack_fails_when_scoring_fallback(tmp_path: Path) -> None:
    run_id = "real-bad"
    _write_graph_state(
        tmp_path,
        run_id,
        {
            "graph_status": "OK",
            "llm_mode": "real",
            "langsmith_runs": {"status": "OK", "runs_published": 1},
            "llm_runtime_by_node": {
                "hypothesis_planner": {"status": "OK", "fallback_used": False, "total_tokens": 1, "latency_ms": 1},
                "test_planner": {"status": "OK", "fallback_used": False, "total_tokens": 1, "latency_ms": 1},
                "expert_explainer": {"status": "OK", "fallback_used": False, "total_tokens": 1, "latency_ms": 1},
                "scoring": {"status": "OK", "fallback_used": True, "total_tokens": 1, "latency_ms": 1},
            },
        },
    )
    out = evaluate_runs(
        base_dir=tmp_path,
        run_ids=[run_id],
        required_nodes=("hypothesis_planner", "test_planner", "expert_explainer", "scoring"),
        require_trace_link=False,
    )
    assert out["overall_ok"] is False
    check = out["checks"][0]
    assert any("scoring: fallback_used debe ser false" in err for err in check["errors"])

