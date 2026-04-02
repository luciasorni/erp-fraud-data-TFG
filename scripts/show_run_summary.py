#!/usr/bin/env python3
"""Resumen legible de un run del grafo (hipótesis, tests, findings, score, explicación)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_hypotheses(graph_dir: Path) -> None:
    rows = _safe_list(_load_json(graph_dir / "hypotheses.json"))
    _print_section(f"Hypotheses ({len(rows)})")
    for idx, row in enumerate(rows[:5], start=1):
        item = _safe_dict(row)
        print(
            f"{idx}. {item.get('hypothesis_id', '')} | "
            f"{item.get('fraud_type', '')} | "
            f"{item.get('title', '')}"
        )


def _print_selected_tests(graph_dir: Path) -> None:
    rows = _safe_list(_load_json(graph_dir / "selected_tests.json"))
    _print_section(f"Selected Tests ({len(rows)})")
    for idx, row in enumerate(rows[:8], start=1):
        item = _safe_dict(row)
        print(
            f"{idx}. hypothesis={item.get('hypothesis_id', '')} -> "
            f"test={item.get('test_id', '')} | source={item.get('source', '')}"
        )


def _print_findings(graph_dir: Path) -> None:
    rows = _safe_list(_load_json(graph_dir / "findings.json"))
    total = sum(int(_safe_dict(row).get("finding_count", 0) or 0) for row in rows)
    _print_section(f"Findings ({len(rows)} tests, total={total})")
    for idx, row in enumerate(rows[:8], start=1):
        item = _safe_dict(row)
        print(
            f"{idx}. {item.get('test_id', '')} | status={item.get('status', '')} | "
            f"finding_count={item.get('finding_count', 0)} | fraud_type={item.get('fraud_type', '')}"
        )


def _print_score(graph_dir: Path) -> None:
    payload = _load_json(graph_dir / "scores.json")
    data = _safe_list(payload)[0] if isinstance(payload, list) and payload else _safe_dict(payload)
    item = _safe_dict(data)
    _print_section("Score")
    print(f"final_label: {item.get('final_label', '')}")
    print(f"confidence: {item.get('confidence', '')}")
    print(f"evidence_summary: {item.get('evidence_summary', '')}")
    probs = _safe_list(item.get("fraud_type_probs", []))
    for row in probs[:5]:
        p = _safe_dict(row)
        print(f"- {p.get('fraud_type', '')}: {p.get('probability', 0)}")


def _print_explanations(graph_dir: Path) -> None:
    rows = _safe_list(_load_json(graph_dir / "explanations.json"))
    _print_section(f"Explanations ({len(rows)})")
    for idx, row in enumerate(rows[:5], start=1):
        item = _safe_dict(row)
        summary = str(item.get("summary", "")).replace("\n", " ").strip()
        if len(summary) > 180:
            summary = summary[:177] + "..."
        print(
            f"{idx}. test={item.get('test_id', '')} | entity={item.get('sample_entity_key', '')}\n"
            f"   {summary}"
        )


def _print_runtime(graph_dir: Path) -> None:
    state = _safe_dict(_load_json(graph_dir / "graph_state.json"))
    meta = _safe_dict(state.get("run_metadata", {}))
    runtime = _safe_dict(meta.get("llm_runtime_by_node", {}))
    _print_section("LLM Runtime")
    print(f"llm_mode: {meta.get('llm_mode', '')}")
    for node_id in ["hypothesis_planner", "test_planner", "expert_explainer", "scoring"]:
        row = _safe_dict(runtime.get(node_id, {}))
        print(
            f"- {node_id}: status={row.get('status', '')}, fallback={row.get('fallback_used', '')}, "
            f"tokens={row.get('total_tokens', 0)}, latency_ms={row.get('latency_ms', 0)}, "
            f"cost_usd={row.get('cost_estimated_usd', 0)}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Muestra resumen legible de outputs de un run.")
    parser.add_argument("--run-id", required=True, help="Run ID dentro de run_results/")
    parser.add_argument("--base-dir", default="run_results", help="Directorio base (default: run_results)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph_dir = Path(str(args.base_dir).strip()) / str(args.run_id).strip() / "graph"
    if not graph_dir.exists():
        raise FileNotFoundError(f"No existe directorio graph para run_id: {graph_dir}")

    print(f"Run: {args.run_id}")
    print(f"Path: {graph_dir}")
    _print_hypotheses(graph_dir)
    _print_selected_tests(graph_dir)
    _print_findings(graph_dir)
    _print_score(graph_dir)
    _print_explanations(graph_dir)
    _print_runtime(graph_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
