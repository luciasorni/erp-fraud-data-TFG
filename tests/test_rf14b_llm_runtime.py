from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.erp_fraud.graph.llm_runtime import _extract_json, resolve_node_runtime_target
from src.erp_fraud.graph.llm_runtime import call_openai_json


def test_rf14b_llm_runtime_defaults_to_stub_mode() -> None:
    target = resolve_node_runtime_target(
        node_id="hypothesis_planner",
        metadata={},
        default_model_used="gpt-5.4-mini",
    )
    assert target["llm_mode"] == "stub"
    assert target["enabled"] is False
    assert target["mode_effective"] == "stub_runtime"


def test_rf14b_llm_runtime_enables_openai_real_mode_from_models_yaml(tmp_path: Path) -> None:
    models_path = tmp_path / "models.yaml"
    models_path.write_text(
        yaml.safe_dump(
            {
                "graph_nodes": {
                    "expert_explainer": {
                        "provider": "openai",
                        "model_used": "gpt-5.4-mini",
                        "real_model_used": "gpt-5.4-mini",
                        "real_temperature": 0.2,
                        "real_max_tokens": 1500,
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    target = resolve_node_runtime_target(
        node_id="expert_explainer",
        metadata={
            "llm_mode": "real",
            "models_config": str(models_path),
        },
        default_model_used="gpt-5.4-mini",
    )
    assert target["llm_mode"] == "real"
    assert target["provider"] == "openai"
    assert target["enabled"] is True
    assert target["model_used"] == "gpt-5.4-mini"
    assert target["mode_effective"] == "real_runtime"


def test_rf14b_llm_runtime_openai_call_without_key_has_safe_fallback(monkeypatch: Any) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    payload, meta = call_openai_json(
        model_used="gpt-5.4-mini",
        temperature=0.0,
        max_tokens=64,
        prompt_text="devuelve json",
        input_payload={"x": 1},
        repair_feedback=[],
        timeout_s=5.0,
        max_retries=1,
        retry_backoff_s=0.01,
    )
    assert payload is None
    assert meta["status"] == "ERROR_NO_API_KEY"
    assert meta["fallback_used"] is True
    assert int(meta["latency_ms"]) >= 0
    assert int(meta["retries_done"]) == 0


def test_rf14b_llm_runtime_extracts_json_from_noisy_response() -> None:
    payload = _extract_json(
        """
        Aquí va el resultado:
        ```json
        {"executive_summary": {"overall_assessment": "ok"}, "items": [{"x": 1}]}
        ```
        texto adicional
        """
    )

    assert payload["executive_summary"]["overall_assessment"] == "ok"
    assert payload["items"][0]["x"] == 1
