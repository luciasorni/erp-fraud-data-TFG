"""Nodo de persistencia de artefactos del grafo."""

from __future__ import annotations

# ruff: noqa: F401

from . import _legacy as _legacy

globals().update(vars(_legacy))

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
        run_dir = ruta_run(run_id)

    graph_dir = run_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "hypotheses_json": graph_dir / "hypotheses.json",
        "selected_tests_json": graph_dir / "selected_tests.json",
        "findings_json": graph_dir / "findings.json",
        "explanation_json": graph_dir / "explanation.json",
        "explanation_md": graph_dir / "explanation.md",
        "explanations_json": graph_dir / "explanations.json",
        "explanations_md": graph_dir / "explanations.md",
        "score_json": graph_dir / "score.json",
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

    _write_json(paths["hypotheses_json"], state.hypotheses)
    _write_json(paths["selected_tests_json"], state.selected_tests)
    _write_json(paths["findings_json"], state.findings)
    _write_json(paths["explanation_json"], state.explanations)
    _write_json(paths["explanations_json"], state.explanations)
    _write_explanations_markdown(
        paths["explanation_md"],
        [row for row in state.explanations if isinstance(row, dict)],
    )
    _write_explanations_markdown(
        paths["explanations_md"],
        [row for row in state.explanations if isinstance(row, dict)],
    )
    _write_json(paths["score_json"], state.scores)
    _write_json(paths["scores_json"], state.scores)
    if "score_compare_json" in paths and isinstance(score_compare_payload, dict):
        _write_json(paths["score_compare_json"], score_compare_payload)
    if "score_experiment_json" in paths and isinstance(score_experiment_payload, dict):
        _write_json(paths["score_experiment_json"], score_experiment_payload)

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
    _write_json(paths["graph_state_json"], state_payload)

    manifest = {
        "version": "1.0.0",
        "run_id": run_id,
        "graph_dir": str(graph_dir),
        "artifacts": {key: str(value) for key, value in sorted(paths.items(), key=lambda item: item[0])},
        "alphacodium": _collect_alphacodium_artifacts(run_dir),
    }
    _write_json(paths["manifest_json"], manifest)

    metadata["persist_status"] = "OK"
    metadata["persist_graph_dir"] = str(graph_dir)
    metadata["persist_manifest_path"] = str(paths["manifest_json"])
    metadata["persist_artifacts"] = manifest["artifacts"]
    metadata["alphacodium_artifacts"] = manifest["alphacodium"]
    return state
