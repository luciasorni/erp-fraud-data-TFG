"""Validación de outputs mínimos de run (RF14c-12)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunOutputValidationError(ValueError):
    """Error controlado de contrato de outputs de run."""


BASE_REQUIRED_OUTPUTS: tuple[str, ...] = (
    "run_metadata.json",
    "schema_summary.json",
    "report.json",
    "ranking.json",
)

GRAPH_REQUIRED_OUTPUTS: tuple[str, ...] = (
    "graph/graph_state.json",
    "graph/hypotheses.json",
    "graph/selected_tests.json",
    "graph/findings.json",
    "graph/scores.json",
)

GRAPH_OPTIONAL_OUTPUTS: tuple[str, ...] = (
    "graph/explanations.json",
    "graph/explanations.md",
    "graph/second_level_analysis.json",
    "graph/second_level_analysis.md",
)


def get_required_run_outputs(*, graph_active: bool) -> dict[str, list[str]]:
    required = list(BASE_REQUIRED_OUTPUTS)
    optional: list[str] = []
    if graph_active:
        required.extend(GRAPH_REQUIRED_OUTPUTS)
        optional.extend(GRAPH_OPTIONAL_OUTPUTS)
    return {"required": required, "optional": optional}


def _detect_graph_active(run_dir: Path) -> bool:
    graph_dir = run_dir / "graph"
    if not graph_dir.exists() or not graph_dir.is_dir():
        return False
    return any(path.is_file() for path in graph_dir.rglob("*"))


def _validate_run_metadata_minimum(run_metadata_path: Path) -> list[str]:
    missing: list[str] = []
    try:
        payload = json.loads(run_metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"run_metadata.json inválido: {exc}"]
    if not isinstance(payload, dict):
        return ["run_metadata.json inválido: se esperaba objeto JSON"]

    for key in ("run_id", "process_scope", "artifact_hash"):
        value = str(payload.get(key, "")).strip()
        if not value:
            missing.append(f"run_metadata.json: falta campo obligatorio '{key}'")
    return missing


def validate_required_run_outputs(
    *,
    run_dir: str | Path,
    graph_active: bool | None = None,
    raise_on_missing: bool = True,
) -> dict[str, Any]:
    run_path = Path(run_dir)
    active = _detect_graph_active(run_path) if graph_active is None else bool(graph_active)
    contract = get_required_run_outputs(graph_active=active)

    missing_required: list[str] = []
    for rel in contract["required"]:
        if not (run_path / rel).is_file():
            missing_required.append(rel)

    run_metadata_path = run_path / "run_metadata.json"
    if run_metadata_path.is_file():
        missing_required.extend(_validate_run_metadata_minimum(run_metadata_path))
    else:
        missing_required.append("run_metadata.json")

    missing_optional: list[str] = []
    for rel in contract["optional"]:
        if not (run_path / rel).is_file():
            missing_optional.append(rel)

    result = {
        "run_dir": str(run_path),
        "graph_active": active,
        "required_outputs": list(contract["required"]),
        "optional_outputs": list(contract["optional"]),
        "missing_required": sorted(set(missing_required)),
        "missing_optional": sorted(set(missing_optional)),
        "ok": len(missing_required) == 0,
    }
    if raise_on_missing and result["missing_required"]:
        raise RunOutputValidationError(
            f"Faltan outputs obligatorios ({len(result['missing_required'])}): {', '.join(result['missing_required'])}"
        )
    return result

