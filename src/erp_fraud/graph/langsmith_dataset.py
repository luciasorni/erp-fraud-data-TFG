"""Construcción/publicación de dataset de evaluación LangSmith (RF14b-07)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..storage.paths import ruta_run


def _safe_str(value: Any) -> str:
    return str(value).strip()


def _collect_kb_snippets(explanations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for exp in explanations:
        if not isinstance(exp, dict):
            continue
        test_id = _safe_str(exp.get("test_id", ""))
        fraud_type = _safe_str(exp.get("fraud_type", ""))
        acfe_ref = exp.get("acfe_reference", {})
        if not isinstance(acfe_ref, dict):
            continue
        hits = acfe_ref.get("hits", [])
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            chunk_id = _safe_str(hit.get("chunk_id", ""))
            source_id = _safe_str(hit.get("source_id", ""))
            source_path = _safe_str(hit.get("source_path", ""))
            key = (chunk_id, source_id, source_path)
            if key in seen:
                continue
            seen.add(key)
            snippets.append(
                {
                    "test_id": test_id,
                    "fraud_type": fraud_type,
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "source_path": source_path,
                }
            )
    return snippets


def build_langsmith_eval_examples(state: Any) -> list[dict[str, Any]]:
    run_id = _safe_str(getattr(state, "run_id", ""))
    hypotheses = [row for row in getattr(state, "hypotheses", []) if isinstance(row, dict)]
    findings = [row for row in getattr(state, "findings", []) if isinstance(row, dict)]
    explanations = [row for row in getattr(state, "explanations", []) if isinstance(row, dict)]
    scores = [row for row in getattr(state, "scores", []) if isinstance(row, dict)]
    run_metadata = getattr(state, "run_metadata", {})
    if not isinstance(run_metadata, dict):
        run_metadata = {}

    kb_snippets = _collect_kb_snippets(explanations)
    score_top = scores[0] if scores else {}
    if not isinstance(score_top, dict):
        score_top = {}

    example = {
        "id": f"{run_id}-snapshot-001",
        "inputs": {
            "run_id": run_id,
            "hypotheses": hypotheses,
            "findings": findings,
            "kb_snippets": kb_snippets,
        },
        "outputs": {
            "final_label": _safe_str(score_top.get("final_label", "")),
            "fraud_type_probs": score_top.get("fraud_type_probs", []),
            "explanations": explanations,
        },
        "metadata": {
            "dataset_hash": _safe_str(run_metadata.get("dataset_hash", "")),
            "graph_status": _safe_str(run_metadata.get("graph_status", "")),
            "scoring_model_used": _safe_str(run_metadata.get("scoring_model_used", "")),
            "scoring_prompt_hash": _safe_str(run_metadata.get("scoring_prompt_hash", "")),
        },
    }
    return [example]


def write_langsmith_eval_dataset_jsonl(*, state: Any, output_path: str | Path | None = None) -> Path:
    run_id = _safe_str(getattr(state, "run_id", ""))
    if not run_id:
        raise ValueError("run_id vacío al construir dataset de evaluación")

    path = Path(output_path) if output_path else (ruta_run(run_id) / "graph" / "langsmith_eval_dataset.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    examples = build_langsmith_eval_examples(state)
    with path.open("w", encoding="utf-8") as fh:
        for row in examples:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    return path


def publish_langsmith_eval_dataset(
    *,
    state: Any,
    dataset_name: str,
    project_name: str,
) -> dict[str, Any]:
    try:
        from langsmith import Client  # type: ignore
    except Exception as exc:
        return {
            "status": "SKIPPED",
            "reason": f"langsmith_sdk_not_installed:{type(exc).__name__}",
            "dataset_name": dataset_name,
            "project_name": project_name,
        }

    examples = build_langsmith_eval_examples(state)
    if not examples:
        return {
            "status": "SKIPPED",
            "reason": "empty_examples",
            "dataset_name": dataset_name,
            "project_name": project_name,
        }

    try:
        client = Client()
        dataset = client.create_dataset(dataset_name=dataset_name, description="ERP fraud evaluation snapshots")
        client.create_examples(
            dataset_id=dataset.id,
            inputs=[row["inputs"] for row in examples],
            outputs=[row["outputs"] for row in examples],
            metadata=[row.get("metadata", {}) for row in examples],
        )
        return {
            "status": "OK",
            "reason": "",
            "dataset_name": dataset_name,
            "project_name": project_name,
            "dataset_id": str(dataset.id),
            "examples_count": len(examples),
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": f"{type(exc).__name__}: {exc}",
            "dataset_name": dataset_name,
            "project_name": project_name,
            "examples_count": len(examples),
        }
