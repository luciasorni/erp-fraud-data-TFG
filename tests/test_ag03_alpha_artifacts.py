from __future__ import annotations

import json
import importlib
from pathlib import Path
from typing import Any

from src.erp_fraud.agents.alpha_loop import alpha_loop
from src.erp_fraud.graph import create_initial_graph_state
from src.erp_fraud.graph.nodes import persist_node


def test_ag03_10_alpha_loop_writes_iteration_artifacts(monkeypatch: Any, tmp_path: Path) -> None:
    alpha_loop_mod = importlib.import_module("src.erp_fraud.agents.alpha_loop")
    base_dir = tmp_path / "run_results"
    monkeypatch.setattr(alpha_loop_mod, "ruta_run", lambda run_id: base_dir / run_id)

    def _generate(_prompt: str, _input: dict[str, Any], _feedback: list[str], iteration: int) -> dict[str, Any]:
        if iteration == 1:
            return {"status": "draft_only"}
        return {"status": "ok", "hypotheses": [{"hypothesis_id": "HYP-001"}]}

    def _validator(output: Any, _input: dict[str, Any]) -> dict[str, Any]:
        hypotheses = output.get("hypotheses", []) if isinstance(output, dict) else []
        if not isinstance(hypotheses, list) or not hypotheses:
            return {"passed": False, "errors": ["missing hypotheses"]}
        return {"passed": True, "errors": []}

    result = alpha_loop(
        run_id="ag03-10-artifacts",
        node_id="hypothesis_planner",
        prompt_text="dummy prompt",
        input_payload={"dataset_hash": "abc"},
        generate_fn=_generate,
        validators={"schema": _validator},
        max_iter=2,
    )

    assert result.status == "OK"
    node_dir = base_dir / "ag03-10-artifacts" / "alphacodium" / "hypothesis_planner"
    assert (node_dir / "iteration_001" / "prompt.md").exists()
    assert (node_dir / "iteration_001" / "output.json").exists()
    assert (node_dir / "iteration_001" / "validation.json").exists()
    assert (node_dir / "iteration_001" / "fix.diff").exists()
    assert (node_dir / "iteration_002" / "prompt.md").exists()
    assert (node_dir / "iteration_002" / "output.json").exists()
    assert (node_dir / "iteration_002" / "validation.json").exists()

    manifest_lines = (node_dir / "iterations_manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest_lines) == 2


def test_ag03_10_persist_node_registers_alphacodium_artifacts(tmp_path: Path) -> None:
    run_id = "ag03-10-persist"
    run_dir = tmp_path / "run_results" / run_id
    alpha_node_dir = run_dir / "alphacodium" / "test_planner" / "iteration_001"
    alpha_node_dir.mkdir(parents=True, exist_ok=True)
    (alpha_node_dir / "prompt.md").write_text("prompt", encoding="utf-8")
    (alpha_node_dir / "output.json").write_text("{}", encoding="utf-8")
    (alpha_node_dir / "validation.json").write_text('{"validation_passed": true}', encoding="utf-8")
    (run_dir / "alphacodium" / "test_planner" / "iterations_manifest.jsonl").write_text(
        json.dumps({"iteration": 1, "status": "OK"}) + "\n",
        encoding="utf-8",
    )

    state = create_initial_graph_state(run_id=run_id)
    state.run_metadata["persist_base_dir"] = str(tmp_path / "run_results")
    out = persist_node(state)

    manifest = json.loads(Path(out.run_metadata["persist_manifest_path"]).read_text(encoding="utf-8"))
    alpha = manifest["alphacodium"]
    assert alpha["exists"] is True
    assert "test_planner" in alpha["nodes"]
    assert alpha["nodes"]["test_planner"]["iterations_count"] == 1
    assert alpha["nodes"]["test_planner"]["manifest_path"]
    assert out.run_metadata["alphacodium_artifacts"]["exists"] is True


def test_ag03_13_alpha_loop_returns_error_when_max_iter_exhausted(
    monkeypatch: Any, tmp_path: Path
) -> None:
    import importlib

    alpha_loop_mod = importlib.import_module("src.erp_fraud.agents.alpha_loop")
    base_dir = tmp_path / "run_results"
    monkeypatch.setattr(alpha_loop_mod, "ruta_run", lambda run_id: base_dir / run_id)

    def _generate(_prompt: str, _input: dict[str, Any], _feedback: list[str], iteration: int) -> dict[str, Any]:
        return {"iteration": iteration, "status": "invalid"}

    def _validator(_output: Any, _input: dict[str, Any]) -> dict[str, Any]:
        return {"passed": False, "errors": ["always failing validator"]}

    result = alpha_loop(
        run_id="ag03-13-max-iter",
        node_id="scoring",
        prompt_text="dummy prompt scoring",
        input_payload={"entity_key": "kreditor=V1|belegnummer=B1"},
        generate_fn=_generate,
        validators={"schema": _validator},
        max_iter=2,
    )

    assert result.status == "ERROR"
    assert result.iterations == 2

    node_dir = base_dir / "ag03-13-max-iter" / "alphacodium" / "scoring"
    manifest_lines = (node_dir / "iterations_manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest_lines) == 2
    first = json.loads(manifest_lines[0])
    second = json.loads(manifest_lines[1])
    assert first["status"] == "REPAIR"
    assert second["status"] == "ERROR"
