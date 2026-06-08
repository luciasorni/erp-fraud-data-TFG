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
    raw = _strip_json_response_text(text)
    if not raw:
        raise ValueError("empty_response")
    try:
        return json.loads(raw)
    except Exception:
        pass
    for opening, closing in (("{", "}"), ("[", "]")):
        candidate = _extract_balanced_json_block(raw, opening=opening, closing=closing)
        if candidate:
            return json.loads(candidate)
    raise ValueError("json_not_found")


def _strip_json_response_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    return raw.strip()


def _extract_balanced_json_block(raw: str, *, opening: str, closing: str) -> str:
    start = raw.find(opening)
    while start >= 0:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(raw)):
            char = raw[idx]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    return raw[start : idx + 1].strip()
        start = raw.find(opening, start + 1)
    return ""


def _compact_payload_for_retry(value: Any, *, depth: int = 0) -> Any:
    if depth >= 5:
        return str(value)[:300]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= 40:
                out["_truncated_keys"] = len(value) - idx
                break
            out[str(key)] = _compact_payload_for_retry(item, depth=depth + 1)
        return out
    if isinstance(value, list):
        out = [_compact_payload_for_retry(item, depth=depth + 1) for item in value[:5]]
        if len(value) > 5:
            out.append({"_truncated_items": len(value) - 5})
        return out
    if isinstance(value, str):
        return value if len(value) <= 800 else value[:800] + "...[truncated]"
    return value


def _build_openai_user_payload(
    *,
    prompt_text: str,
    input_payload: dict[str, Any],
    repair_feedback: list[str],
    attempt: int,
) -> dict[str, Any]:
    instruction = "Devuelve SOLO JSON válido, sin markdown ni texto extra."
    resolved_payload: dict[str, Any] = input_payload
    resolved_feedback = list(repair_feedback)
    if attempt > 1:
        instruction = (
            "Responde ÚNICAMENTE con el JSON. Sin texto adicional, sin markdown, sin explicaciones. "
            "La respuesta anterior no fue JSON válido o no pudo parsearse."
        )
        resolved_feedback.append("Reintento: devuelve exclusivamente un objeto JSON válido.")
        resolved_payload = _compact_payload_for_retry(input_payload)
    return {
        "instruction": instruction,
        "prompt_text": prompt_text,
        "input_payload": resolved_payload,
        "repair_feedback": resolved_feedback,
    }


def _log_raw_response_parse_failure(*, model_used: str, attempt: int, response_text: str) -> None:
    payload = {
        "event": "openai_json_parse_failure",
        "model_used": model_used,
        "attempt": attempt,
        "response_text": str(response_text or ""),
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


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
    json_schema: dict[str, Any] | None = None,
    json_schema_name: str = "structured_output",
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
    last_status = "ERROR_OPENAI_CALL:Unknown"
    max_attempts = max(1, int(max_retries) + 1)
    for attempt in range(1, max_attempts + 1):
        try:
            user_payload = _build_openai_user_payload(
                prompt_text=prompt_text,
                input_payload=input_payload,
                repair_feedback=repair_feedback,
                attempt=attempt,
            )
            request_kwargs: dict[str, Any] = {
                "model": model_used,
                "input": json.dumps(user_payload, ensure_ascii=False, sort_keys=True, default=str),
            }
            if json_schema:
                request_kwargs["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": str(json_schema_name or "structured_output").strip() or "structured_output",
                        "schema": json_schema,
                        "strict": True,
                    }
                }
            if max_tokens > 0:
                request_kwargs["max_output_tokens"] = int(max_tokens)
            if temperature > 0:
                request_kwargs["temperature"] = float(temperature)
            response = client.responses.create(
                **request_kwargs,
                timeout=max(1.0, float(timeout_s)),
            )
            response_text = str(getattr(response, "output_text", "") or "").strip()
            if not response_text and hasattr(response, "model_dump"):
                response_text = json.dumps(response.model_dump(), ensure_ascii=False, default=str)
            try:
                parsed = _extract_json(response_text)
            except Exception:
                _log_raw_response_parse_failure(
                    model_used=model_used,
                    attempt=attempt,
                    response_text=response_text,
                )
                raise
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
