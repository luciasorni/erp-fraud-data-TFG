"""Registro de prompts versionados para nodos del grafo (RF14b-03)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPT_REGISTRY_PATH = PROJECT_ROOT / "config" / "prompt_versions.yaml"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_path(value: str) -> Path:
    path = Path(str(value).strip())
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _load_registry(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: YAML raíz debe ser objeto")
    return payload


def load_node_prompt(
    *,
    node_id: str,
    fallback_text: str,
    registry_path: str | Path | None = None,
) -> dict[str, str]:
    """Carga prompt versionado para `node_id` y devuelve metadata + texto.

    Devuelve siempre un payload válido; ante error usa `fallback_text`.
    """
    reg_path = _resolve_path(str(registry_path)) if registry_path else DEFAULT_PROMPT_REGISTRY_PATH
    base: dict[str, str] = {
        "text": str(fallback_text),
        "path": "",
        "version": "inline_fallback",
        "hash": _sha256_text(str(fallback_text)),
        "status": "FALLBACK",
    }
    if not reg_path.exists():
        return base

    try:
        registry = _load_registry(reg_path)
        nodes = registry.get("nodes", {})
        if not isinstance(nodes, dict):
            return base
        entry = nodes.get(node_id)
        if not isinstance(entry, dict):
            return base
        prompt_file = str(entry.get("file", "")).strip()
        if not prompt_file:
            return base
        prompt_path = _resolve_path(prompt_file)
        if not prompt_path.exists():
            return base
        text = prompt_path.read_text(encoding="utf-8")
        if not text.strip():
            return base
        version = str(entry.get("version", "")).strip() or "unspecified"
        return {
            "text": text,
            "path": str(prompt_path),
            "version": version,
            "hash": _sha256_text(text),
            "status": "OK",
        }
    except Exception:
        return base
