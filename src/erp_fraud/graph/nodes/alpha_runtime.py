"""Helpers de runtime LLM/Alpha para nodos."""

from __future__ import annotations

from typing import Any

from . import deps
from .common import (
    record_graph_node_model_config as _record_graph_node_model_config,
    sha256_text as _sha256_text,
    stable_json as _stable_json,
)
from ..prompt_registry import load_node_prompt as _load_node_prompt


def run_alpha_loop_for_node(**kwargs: Any) -> Any:
    state = kwargs["state"]
    node_id = str(kwargs["node_id"])
    prompt_text = str(kwargs["prompt_text"])
    input_payload = kwargs["input_payload"]
    generate_fn = kwargs["generate_fn"]
    validators = kwargs["validators"]
    max_iter = int(kwargs.get("max_iter", 3) or 3)

    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    alpha_meta = metadata.setdefault("alphacodium", {})
    if not isinstance(alpha_meta, dict):
        alpha_meta = {}
        metadata["alphacodium"] = alpha_meta

    enabled = bool(metadata.get("alphacodium_enabled", True))
    if not enabled or deps.alpha_loop is None or deps.alpha_loop_result_to_dict is None:
        output = generate_fn(prompt_text, dict(input_payload), [], 1)
        alpha_meta[node_id] = {
            "status": "BYPASSED",
            "iterations": 1,
            "artifacts_dir": "",
        }
        return output

    loop_result = deps.alpha_loop(
        run_id=str(state.run_id),
        node_id=node_id,
        prompt_text=prompt_text,
        input_payload=input_payload,
        generate_fn=generate_fn,
        validators=validators,
        max_iter=max_iter,
    )
    alpha_meta[node_id] = deps.alpha_loop_result_to_dict(loop_result)
    if str(loop_result.status).upper() != "OK":
        raise RuntimeError(f"alpha_loop {node_id} terminó en estado={loop_result.status}")
    return loop_result.final_output


# Re-export explícito para mantener imports actuales de nodos.
load_node_prompt = _load_node_prompt
record_graph_node_model_config = _record_graph_node_model_config
sha256_text = _sha256_text
stable_json = _stable_json
