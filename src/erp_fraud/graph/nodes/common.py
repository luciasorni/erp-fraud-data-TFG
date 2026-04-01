"""Utilidades comunes para nodos de grafo.

Extraídas de `_legacy.py` para reducir acoplamiento y tamaño del módulo.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[4]


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
    tracing_raw = str(os.getenv("LANGSMITH_TRACING", "")).strip().lower()
    tracing_v2_raw = str(os.getenv("LANGCHAIN_TRACING_V2", "")).strip().lower()
    tracing_enabled = tracing_raw in {"1", "true", "yes", "on"} or tracing_v2_raw in {
        "1",
        "true",
        "yes",
        "on",
    }
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
    try:
        temperature = float(node_cfg.get("temperature", 0.0) or 0.0)
    except (TypeError, ValueError):
        temperature = 0.0
    try:
        max_tokens = int(node_cfg.get("max_tokens", 0) or 0)
    except (TypeError, ValueError):
        max_tokens = 0

    return {
        "node_id": node_id,
        "mode": str(node_cfg.get("mode", "stub")).strip() or "stub",
        "model_used": model_used,
        "temperature": temperature,
        "max_tokens": max_tokens,
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
