#!/usr/bin/env python3
"""Verificación rápida del stack real (LLM + LangSmith) sobre runs existentes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_NODES = ("hypothesis_planner", "test_planner", "expert_explainer", "scoring")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_run_metadata(base_dir: Path, run_id: str) -> dict[str, Any]:
    path = base_dir / run_id / "graph" / "graph_state.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("run_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata


def _validate_one_run(
    *,
    run_id: str,
    run_metadata: dict[str, Any],
    required_nodes: tuple[str, ...],
    require_trace_link: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    llm_runtime = run_metadata.get("llm_runtime_by_node", {})
    if not isinstance(llm_runtime, dict):
        llm_runtime = {}

    graph_status = str(run_metadata.get("graph_status", "")).strip().upper()
    if graph_status != "OK":
        errors.append(f"graph_status debe ser OK y es '{graph_status or 'MISSING'}'")

    llm_mode = str(run_metadata.get("llm_mode", "")).strip().lower()
    if llm_mode != "real":
        errors.append(f"llm_mode debe ser real y es '{llm_mode or 'MISSING'}'")

    langsmith_runs = run_metadata.get("langsmith_runs", {})
    if not isinstance(langsmith_runs, dict):
        langsmith_runs = {}
    ls_status = str(langsmith_runs.get("status", "")).strip().upper()
    if ls_status != "OK":
        errors.append(f"langsmith_runs.status debe ser OK y es '{ls_status or 'MISSING'}'")
    if int(langsmith_runs.get("runs_published", 0) or 0) < 1:
        errors.append("langsmith_runs.runs_published debe ser >= 1")

    trace_link = str(run_metadata.get("langsmith_trace_link", "")).strip() or str(
        langsmith_runs.get("trace_link", "")
    ).strip()
    if require_trace_link and not trace_link:
        errors.append("langsmith_trace_link vacío")

    for node_id in required_nodes:
        row = llm_runtime.get(node_id, {})
        if not isinstance(row, dict):
            errors.append(f"{node_id}: no existe en llm_runtime_by_node")
            continue
        status = str(row.get("status", "")).strip().upper()
        fallback_used = bool(row.get("fallback_used", True))
        total_tokens = int(row.get("total_tokens", 0) or 0)
        latency_ms = int(row.get("latency_ms", 0) or 0)
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
        "graph_status": graph_status,
        "trace_link": trace_link,
    }


def evaluate_runs(
    *,
    base_dir: Path,
    run_ids: list[str],
    required_nodes: tuple[str, ...],
    require_trace_link: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for run_id in run_ids:
        try:
            metadata = _load_run_metadata(base_dir=base_dir, run_id=run_id)
            checks.append(
                _validate_one_run(
                    run_id=run_id,
                    run_metadata=metadata,
                    required_nodes=required_nodes,
                    require_trace_link=require_trace_link,
                )
            )
        except Exception as exc:
            checks.append(
                {
                    "run_id": run_id,
                    "passed": False,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
            )

    passed = [row for row in checks if bool(row.get("passed", False))]
    return {
        "generated_at_utc": _utc_now_iso(),
        "base_dir": str(base_dir),
        "run_ids": run_ids,
        "required_nodes": list(required_nodes),
        "require_trace_link": require_trace_link,
        "checks": checks,
        "passed_runs": len(passed),
        "overall_ok": len(passed) == len(run_ids),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verifica que runs reales cumplen criterios de stack real.")
    parser.add_argument("--base-dir", default="run_results", help="Directorio base de runs.")
    parser.add_argument("--run-ids", nargs="+", required=True, help="Uno o más run_id a verificar.")
    parser.add_argument(
        "--no-require-trace-link",
        action="store_true",
        help="No exigir langsmith_trace_link.",
    )
    parser.add_argument(
        "--output",
        default="run_results/real_stack_check.json",
        help="Ruta de salida JSON para el resultado.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_ids = [str(item).strip() for item in args.run_ids if str(item).strip()]
    if not run_ids:
        raise ValueError("Debes pasar al menos un run_id")

    payload = evaluate_runs(
        base_dir=Path(str(args.base_dir).strip()),
        run_ids=run_ids,
        required_nodes=DEFAULT_REQUIRED_NODES,
        require_trace_link=not bool(args.no_require_trace_link),
    )
    out_path = Path(str(args.output).strip())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if bool(payload.get("overall_ok", False)):
        print("OK real-stack check PASSED")
        print(out_path)
        return 0

    print("ERROR real-stack check FAILED")
    print(out_path)
    for row in payload.get("checks", []):
        if not isinstance(row, dict):
            continue
        if bool(row.get("passed", False)):
            continue
        print(f"- {row.get('run_id')}:")
        for err in row.get("errors", []):
            print(f"  - {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
