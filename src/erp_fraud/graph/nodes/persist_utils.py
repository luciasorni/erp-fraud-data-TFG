"""Helpers de persistencia para nodos de grafo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_columns(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        col = str(item).strip()
        if not col:
            continue
        if col in seen:
            continue
        seen.add(col)
        out.append(col)
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_explanations_markdown(path: Path, explanations: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["# Explanations", ""]
    if not explanations:
        lines.extend(["No explanations generated.", ""])
    else:
        for idx, row in enumerate(explanations, start=1):
            if not isinstance(row, dict):
                continue
            test_id = str(row.get("test_id", "")).strip() or "<unknown_test>"
            status = str(row.get("status", "")).strip() or "UNKNOWN"
            fraud_type = str(row.get("fraud_type", "")).strip() or "unknown"
            finding_count = int(row.get("finding_count", 0) or 0)
            summary = str(row.get("summary", "")).strip()
            evidence_cols = normalize_columns(row.get("cited_evidence_columns", []))
            keys_payload = row.get("cited_keys", {})
            if not isinstance(keys_payload, dict):
                keys_payload = {}
            lines.append(f"## {idx}. {test_id}")
            lines.append(f"- status: `{status}`")
            lines.append(f"- fraud_type: `{fraud_type}`")
            lines.append(f"- finding_count: `{finding_count}`")
            lines.append(f"- cited_evidence_columns: `{', '.join(evidence_cols) if evidence_cols else '-'}`")
            if keys_payload:
                lines.append(f"- cited_keys: `{json.dumps(keys_payload, ensure_ascii=False, sort_keys=True)}`")
            if summary:
                lines.append(f"- summary: {summary}")
            acfe_reference = row.get("acfe_reference", {})
            if isinstance(acfe_reference, dict):
                acfe_status = str(acfe_reference.get("status", "")).strip()
                if acfe_status:
                    lines.append(f"- acfe_reference_status: `{acfe_status}`")
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def collect_alphacodium_artifacts(run_dir: Path) -> dict[str, Any]:
    alpha_dir = run_dir / "alphacodium"
    if not alpha_dir.exists():
        return {
            "base_dir": str(alpha_dir),
            "exists": False,
            "nodes": {},
            "files_total": 0,
        }

    nodes_payload: dict[str, Any] = {}
    files_total = 0
    for node_dir in sorted(alpha_dir.iterdir(), key=lambda p: p.name):
        if not node_dir.is_dir():
            continue
        manifest_path = node_dir / "iterations_manifest.jsonl"
        iteration_dirs = sorted(
            [path for path in node_dir.iterdir() if path.is_dir() and path.name.startswith("iteration_")],
            key=lambda p: p.name,
        )
        iterations_payload: list[dict[str, Any]] = []
        for iteration_dir in iteration_dirs:
            expected_files = {
                "prompt": iteration_dir / "prompt.md",
                "output": iteration_dir / "output.json",
                "validation": iteration_dir / "validation.json",
                "fix": iteration_dir / "fix.diff",
            }
            row = {
                "iteration_dir": str(iteration_dir),
                "prompt_path": str(expected_files["prompt"]) if expected_files["prompt"].exists() else "",
                "output_path": str(expected_files["output"]) if expected_files["output"].exists() else "",
                "validation_path": str(expected_files["validation"])
                if expected_files["validation"].exists()
                else "",
                "fix_path": str(expected_files["fix"]) if expected_files["fix"].exists() else "",
            }
            files_total += sum(1 for path in expected_files.values() if path.exists())
            iterations_payload.append(row)

        if manifest_path.exists():
            files_total += 1
        nodes_payload[node_dir.name] = {
            "manifest_path": str(manifest_path) if manifest_path.exists() else "",
            "iterations": iterations_payload,
            "iterations_count": len(iterations_payload),
        }

    return {
        "base_dir": str(alpha_dir),
        "exists": True,
        "nodes": nodes_payload,
        "files_total": files_total,
    }
