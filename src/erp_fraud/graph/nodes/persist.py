"""Nodo de persistencia de artefactos del grafo."""

from __future__ import annotations

from pathlib import Path

from .io_utils import (
    collect_alphacodium_artifacts,
    run_dir_from_id,
    write_explanations_markdown,
    write_json,
)
from ..state import GraphState

def persist_node(state: GraphState) -> GraphState:
    """Nodo de persistencia de artefactos de grafo (RF14-10)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    run_id = str(state.run_id).strip()
    if not run_id:
        raise ValueError("run_id vacío en persist_node")

    persist_base_dir = str(metadata.get("persist_base_dir", "")).strip()
    if persist_base_dir:
        run_dir = Path(persist_base_dir) / run_id
    else:
        run_dir = run_dir_from_id(run_id)

    graph_dir = run_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "hypotheses_json": graph_dir / "hypotheses.json",
        "selected_tests_json": graph_dir / "selected_tests.json",
        "findings_json": graph_dir / "findings.json",
        "explanations_json": graph_dir / "explanations.json",
        "explanations_md": graph_dir / "explanations.md",
        "scores_json": graph_dir / "scores.json",
        "graph_state_json": graph_dir / "graph_state.json",
        "manifest_json": graph_dir / "manifest.json",
    }
    score_compare_payload = metadata.get("score_compare")
    if isinstance(score_compare_payload, dict) and score_compare_payload:
        paths["score_compare_json"] = graph_dir / "score_compare.json"
    score_experiment_payload = metadata.get("scoring_experiment")
    if isinstance(score_experiment_payload, dict) and score_experiment_payload:
        paths["score_experiment_json"] = graph_dir / "score_experiment.json"

    write_json(paths["hypotheses_json"], state.hypotheses)
    write_json(paths["selected_tests_json"], state.selected_tests)
    write_json(paths["findings_json"], state.findings)
    write_json(paths["explanations_json"], state.explanations)
    write_explanations_markdown(
        paths["explanations_md"],
        [row for row in state.explanations if isinstance(row, dict)],
    )
    write_json(paths["scores_json"], state.scores)
    if "score_compare_json" in paths and isinstance(score_compare_payload, dict):
        write_json(paths["score_compare_json"], score_compare_payload)
    if "score_experiment_json" in paths and isinstance(score_experiment_payload, dict):
        write_json(paths["score_experiment_json"], score_experiment_payload)

    state_payload = {
        "run_id": state.run_id,
        "schema": state.schema,
        "kb_status": state.kb_status,
        "hypotheses_count": len(state.hypotheses),
        "selected_tests_count": len(state.selected_tests),
        "findings_count": len(state.findings),
        "explanations_count": len(state.explanations),
        "scores_count": len(state.scores),
        "run_metadata": metadata,
    }
    write_json(paths["graph_state_json"], state_payload)

    manifest = {
        "version": "1.0.0",
        "run_id": run_id,
        "graph_dir": str(graph_dir),
        "artifacts": {key: str(value) for key, value in sorted(paths.items(), key=lambda item: item[0])},
        "alphacodium": collect_alphacodium_artifacts(run_dir),
    }
    write_json(paths["manifest_json"], manifest)

    metadata["persist_status"] = "OK"
    metadata["persist_graph_dir"] = str(graph_dir)
    metadata["persist_manifest_path"] = str(paths["manifest_json"])
    metadata["persist_artifacts"] = manifest["artifacts"]
    metadata["alphacodium_artifacts"] = manifest["alphacodium"]
    return state
