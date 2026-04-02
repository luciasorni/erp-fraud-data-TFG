#!/usr/bin/env python3
"""Verifica criterio cloud-readiness sobre runs reales (RF14b)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_NODES = ("hypothesis_planner", "test_planner", "expert_explainer", "scoring")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_graph_metadata(run_dir: Path) -> dict[str, Any]:
    graph_state_path = run_dir / "graph" / "graph_state.json"
    payload = json.loads(graph_state_path.read_text(encoding="utf-8"))
    run_metadata = payload.get("run_metadata", {})
    if not isinstance(run_metadata, dict):
        run_metadata = {}
    return run_metadata


def _validate_run(
    *,
    run_id: str,
    run_metadata: dict[str, Any],
    required_nodes: tuple[str, ...],
) -> dict[str, Any]:
    errors: list[str] = []
    llm_runtime = run_metadata.get("llm_runtime_by_node", {})
    if not isinstance(llm_runtime, dict):
        llm_runtime = {}

    graph_status = str(run_metadata.get("graph_status", "")).strip().upper()
    if not graph_status:
        abort_reason = str(run_metadata.get("graph_abort_reason", "")).strip()
        node_status = run_metadata.get("node_status", {})
        router_status = ""
        if isinstance(node_status, dict):
            router_status = str(node_status.get("graph_router", "")).strip().upper()
        if abort_reason or router_status == "ABORTED":
            errors.append("graph_status MISSING pero el run está abortado")
    elif graph_status != "OK":
        errors.append(f"graph_status debe ser OK y es '{graph_status}'")

    llm_mode = str(run_metadata.get("llm_mode", "")).strip().lower()
    if llm_mode != "real":
        errors.append(f"llm_mode debe ser real y es '{llm_mode or 'MISSING'}'")

    has_real_tag = False
    tags = run_metadata.get("langsmith_tags", [])
    if isinstance(tags, list):
        has_real_tag = "llm_mode:real" in [str(t).strip() for t in tags]
    if not has_real_tag:
        errors.append("langsmith_tags debe incluir llm_mode:real")

    for node_id in required_nodes:
        node = llm_runtime.get(node_id, {})
        if not isinstance(node, dict):
            errors.append(f"{node_id}: no existe en llm_runtime_by_node")
            continue
        status = str(node.get("status", "")).strip().upper()
        fallback_used = bool(node.get("fallback_used", True))
        total_tokens = int(node.get("total_tokens", 0) or 0)
        latency_ms = int(node.get("latency_ms", 0) or 0)
        if status != "OK":
            errors.append(f"{node_id}: status debe ser OK y es '{status or 'MISSING'}'")
        if fallback_used:
            errors.append(f"{node_id}: fallback_used debe ser false")
        if total_tokens <= 0:
            errors.append(f"{node_id}: total_tokens debe ser > 0")
        if latency_ms <= 0:
            errors.append(f"{node_id}: latency_ms debe ser > 0")

    return {
        "run_id": run_id,
        "passed": len(errors) == 0,
        "errors": errors,
    }


def evaluate_runs(
    *,
    base_dir: Path,
    run_ids: list[str],
    required_nodes: tuple[str, ...] = DEFAULT_REQUIRED_NODES,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for run_id in run_ids:
        run_dir = base_dir / run_id
        try:
            run_metadata = _load_graph_metadata(run_dir)
            checks.append(_validate_run(run_id=run_id, run_metadata=run_metadata, required_nodes=required_nodes))
        except Exception as exc:
            checks.append(
                {
                    "run_id": run_id,
                    "passed": False,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
            )

    passed_runs = [row for row in checks if bool(row.get("passed", False))]
    return {
        "generated_at_utc": _utc_now_iso(),
        "base_dir": str(base_dir),
        "required_nodes": list(required_nodes),
        "run_ids": run_ids,
        "checks": checks,
        "passed_runs": len(passed_runs),
        "required_passes": len(run_ids),
        "cloud_ready": len(passed_runs) == len(run_ids) and len(run_ids) >= 3,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check cloud-readiness from real LLM runs.")
    parser.add_argument(
        "--base-dir",
        default="run_results",
        help="Directorio base de runs (default: run_results).",
    )
    parser.add_argument(
        "--run-ids",
        nargs="+",
        required=True,
        help="Lista de run_ids reales a verificar (mínimo recomendado: 3).",
    )
    parser.add_argument(
        "--output",
        default="run_results/cloud_readiness_check.json",
        help="Ruta de salida JSON con veredicto.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(str(args.base_dir).strip())
    run_ids = [str(item).strip() for item in args.run_ids if str(item).strip()]
    if len(run_ids) < 3:
        raise ValueError("Debes pasar al menos 3 run_ids para validar cloud-readiness.")

    payload = evaluate_runs(base_dir=base_dir, run_ids=run_ids)
    out_path = Path(str(args.output).strip())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if bool(payload.get("cloud_ready", False)):
        print("OK cloud-readiness check PASSED")
        print(out_path)
        return 0
    print("ERROR cloud-readiness check FAILED")
    print(out_path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
