"""Utilidades comunes para nodos de grafo.

Módulo base compartido por nodos (sin dependencia legacy).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml
from ...config.env import parse_bool_env


PROJECT_ROOT = Path(__file__).resolve().parents[4]
VALID_LLM_MODES: tuple[str, str] = ("stub", "real")


def resolve_project_path(path_value: str | Path) -> str:
    raw = str(path_value).strip()
    if not raw:
        return ""
    path = Path(raw)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def langsmith_snapshot() -> dict[str, Any]:
    tracing_enabled = parse_bool_env(os.getenv("LANGSMITH_TRACING", ""), default=False) or parse_bool_env(
        os.getenv("LANGCHAIN_TRACING_V2", ""),
        default=False,
    )
    api_key_present = bool(str(os.getenv("LANGSMITH_API_KEY", "")).strip())
    project = str(os.getenv("LANGSMITH_PROJECT", "")).strip()
    endpoint = str(os.getenv("LANGSMITH_ENDPOINT", "")).strip()
    trace_link = str(os.getenv("LANGSMITH_TRACE_LINK", "")).strip()
    return {
        "tracing_enabled": tracing_enabled,
        "api_key_present": api_key_present,
        "project": project,
        "endpoint": endpoint,
        "trace_link": trace_link,
    }


def resolve_graph_node_model_config(
    *,
    node_id: str,
    metadata: dict[str, Any],
    default_model_used: str,
) -> dict[str, Any]:
    models_config_path = resolve_project_path(
        str(metadata.get("models_config", "config/models.yaml")).strip() or "config/models.yaml"
    )
    payload: dict[str, Any] = {}
    try:
        path = Path(models_config_path)
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
    except Exception:
        payload = {}

    graph_nodes = payload.get("graph_nodes", {}) if isinstance(payload, dict) else {}
    node_cfg = graph_nodes.get(node_id, {}) if isinstance(graph_nodes, dict) else {}
    if not isinstance(node_cfg, dict):
        node_cfg = {}

    model_used = str(node_cfg.get("model_used", "")).strip() or default_model_used
    provider = str(node_cfg.get("provider", "")).strip().lower() or "stub"
    real_model_used = (
        str(node_cfg.get("real_model_used", "")).strip()
        or str(node_cfg.get("model_used_real", "")).strip()
        or model_used
    )
    try:
        temperature = float(node_cfg.get("temperature", 0.0) or 0.0)
    except (TypeError, ValueError):
        temperature = 0.0
    try:
        real_temperature = float(
            node_cfg.get("real_temperature", node_cfg.get("temperature_real", temperature)) or temperature
        )
    except (TypeError, ValueError):
        real_temperature = temperature
    try:
        max_tokens = int(node_cfg.get("max_tokens", 0) or 0)
    except (TypeError, ValueError):
        max_tokens = 0
    try:
        real_max_tokens = int(node_cfg.get("real_max_tokens", node_cfg.get("max_tokens_real", max_tokens)) or max_tokens)
    except (TypeError, ValueError):
        real_max_tokens = max_tokens

    return {
        "node_id": node_id,
        "mode": str(node_cfg.get("mode", "stub")).strip() or "stub",
        "provider": provider,
        "model_used": model_used,
        "real_model_used": real_model_used,
        "temperature": temperature,
        "real_temperature": real_temperature,
        "max_tokens": max_tokens,
        "real_max_tokens": real_max_tokens,
        "models_config_path": models_config_path,
        "source": "config" if node_cfg else "fallback",
    }


def record_graph_node_model_config(
    *,
    node_id: str,
    metadata: dict[str, Any],
    default_model_used: str,
    overrides: dict[str, Any] | None = None,
) -> None:
    agent_model_config = metadata.setdefault("agent_model_config", {})
    if not isinstance(agent_model_config, dict):
        agent_model_config = {}
        metadata["agent_model_config"] = agent_model_config

    config = resolve_graph_node_model_config(
        node_id=node_id,
        metadata=metadata,
        default_model_used=default_model_used,
    )
    if isinstance(overrides, dict):
        config.update(overrides)
    agent_model_config[node_id] = config


def resolve_llm_mode(metadata: dict[str, Any], *, default: str = "stub") -> str:
    raw = str(metadata.get("llm_mode", default)).strip().lower()
    if raw in VALID_LLM_MODES:
        return raw
    return default


def annotate_node_llm_mode(*, metadata: dict[str, Any], node_id: str) -> str:
    mode = resolve_llm_mode(metadata)
    metadata["llm_mode"] = mode
    by_node = metadata.setdefault("node_llm_mode", {})
    if isinstance(by_node, dict):
        by_node[node_id] = mode
    tags = metadata.setdefault("langsmith_tags", [])
    if isinstance(tags, list):
        llm_tag = f"llm_mode:{mode}"
        if llm_tag not in tags:
            tags.append(llm_tag)
        node_tag = f"node:{node_id}"
        if node_tag not in tags:
            tags.append(node_tag)
    return mode
