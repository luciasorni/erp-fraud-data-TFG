"""Runtime LLM helpers (stub|real) para nodos del grafo."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .nodes.common import resolve_graph_node_model_config, resolve_llm_mode


def resolve_node_runtime_target(
    *,
    node_id: str,
    metadata: dict[str, Any],
    default_model_used: str,
) -> dict[str, Any]:
    cfg = resolve_graph_node_model_config(
        node_id=node_id,
        metadata=metadata,
        default_model_used=default_model_used,
    )
    llm_mode = resolve_llm_mode(metadata)
    provider = str(cfg.get("provider", "stub")).strip().lower() or "stub"
    target = {
        "llm_mode": llm_mode,
        "provider": provider,
        "model_used": str(cfg.get("real_model_used", "")).strip() or str(cfg.get("model_used", "")).strip(),
        "temperature": float(cfg.get("real_temperature", cfg.get("temperature", 0.0)) or 0.0),
        "max_tokens": int(cfg.get("real_max_tokens", cfg.get("max_tokens", 0)) or 0),
        "mode_effective": "stub_runtime",
        "enabled": False,
        "reason": "llm_mode_stub",
    }
    if llm_mode != "real":
        return target
    if provider != "openai":
        target["reason"] = "provider_not_supported"
        return target
    if not target["model_used"]:
        target["reason"] = "missing_model"
        return target
    target["enabled"] = True
    target["mode_effective"] = "real_runtime"
    target["reason"] = "ok"
    return target


def _extract_json(text: str) -> Any:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty_response")
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    start_obj = raw.find("{")
    end_obj = raw.rfind("}")
    if start_obj >= 0 and end_obj > start_obj:
        try:
            return json.loads(raw[start_obj : end_obj + 1])
        except Exception:
            pass
    start_arr = raw.find("[")
    end_arr = raw.rfind("]")
    if start_arr >= 0 and end_arr > start_arr:
        return json.loads(raw[start_arr : end_arr + 1])
    raise ValueError("json_not_found")


def call_openai_json(
    *,
    model_used: str,
    temperature: float,
    max_tokens: int,
    prompt_text: str,
    input_payload: dict[str, Any],
    repair_feedback: list[str],
    timeout_s: float = 30.0,
    max_retries: int = 1,
    retry_backoff_s: float = 0.6,
) -> tuple[Any | None, dict[str, Any]]:
    started = time.perf_counter()
    retries_done = 0
    meta_base: dict[str, Any] = {
        "provider": "openai",
        "model_used": model_used,
        "retries_done": 0,
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_estimated_usd": 0.0,
        "fallback_used": False,
    }

    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        meta_base.update(
            {
                "status": "ERROR_NO_API_KEY",
                "fallback_used": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        return None, meta_base

    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        meta_base.update(
            {
                "status": "ERROR_OPENAI_NOT_INSTALLED",
                "fallback_used": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        return None, meta_base

    client = OpenAI(api_key=api_key)
    user_payload = {
        "instruction": "Devuelve SOLO JSON válido, sin markdown ni texto extra.",
        "prompt_text": prompt_text,
        "input_payload": input_payload,
        "repair_feedback": repair_feedback,
    }
    request_kwargs: dict[str, Any] = {
        "model": model_used,
        "input": json.dumps(user_payload, ensure_ascii=False, sort_keys=True, default=str),
    }
    if max_tokens > 0:
        request_kwargs["max_output_tokens"] = int(max_tokens)
    if temperature > 0:
        request_kwargs["temperature"] = float(temperature)

    last_status = "ERROR_OPENAI_CALL:Unknown"
    max_attempts = max(1, int(max_retries) + 1)
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.responses.create(
                **request_kwargs,
                timeout=max(1.0, float(timeout_s)),
            )
            response_text = str(getattr(response, "output_text", "") or "").strip()
            if not response_text and hasattr(response, "model_dump"):
                response_text = json.dumps(response.model_dump(), ensure_ascii=False, default=str)
            parsed = _extract_json(response_text)
            usage = getattr(response, "usage", None)
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
            total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
            # Coste estimado configurable por env (por 1M tokens). Default 0 para no asumir precios.
            in_price = float(os.getenv("OPENAI_PRICE_INPUT_PER_1M_USD", "0") or 0.0)
            out_price = float(os.getenv("OPENAI_PRICE_OUTPUT_PER_1M_USD", "0") or 0.0)
            cost_estimated_usd = ((input_tokens * in_price) + (output_tokens * out_price)) / 1_000_000.0
            meta_base.update(
                {
                    "status": "OK",
                    "retries_done": retries_done,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_estimated_usd": float(cost_estimated_usd),
                    "fallback_used": False,
                }
            )
            return parsed, meta_base
        except Exception as exc:
            last_status = f"ERROR_OPENAI_CALL:{type(exc).__name__}"
            if attempt >= max_attempts:
                break
            retries_done += 1
            time.sleep(max(0.0, float(retry_backoff_s)))

    meta_base.update(
        {
            "status": last_status,
            "retries_done": retries_done,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "fallback_used": True,
        }
    )
    return None, meta_base
