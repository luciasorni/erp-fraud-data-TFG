"""Taxonomía oficial de tipos de fraude (Fraud Tree) y utilidades de mapeo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .nodes.common import resolve_project_path


DEFAULT_FRAUD_TAXONOMY_PATH = "config/fraud_tree_taxonomy.yaml"
DEFAULT_FALLBACK_BRANCH_ID = "other_frauds"


def load_fraud_taxonomy(*, config_path: str | None = None) -> dict[str, Any]:
    raw_path = str(config_path or DEFAULT_FRAUD_TAXONOMY_PATH).strip() or DEFAULT_FRAUD_TAXONOMY_PATH
    resolved = Path(resolve_project_path(raw_path))
    payload: dict[str, Any] = {}
    if resolved.exists():
        try:
            loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}
    if not payload:
        return {
            "version": "0.0.0",
            "source": {"document": ""},
            "branches": [],
            "internal_fraud_type_to_branch": {},
            "config_path": str(resolved),
        }
    payload["config_path"] = str(resolved)
    return payload


def _branches_map(taxonomy: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    branches = taxonomy.get("branches", []) if isinstance(taxonomy, dict) else []
    if not isinstance(branches, list):
        return out
    for row in branches:
        if not isinstance(row, dict):
            continue
        branch_id = str(row.get("id", "")).strip()
        label = str(row.get("label", "")).strip()
        if branch_id:
            out[branch_id] = label or branch_id
    return out


def branch_for_fraud_type(*, fraud_type: str, taxonomy: dict[str, Any]) -> dict[str, str]:
    normalized = str(fraud_type).strip()
    mapping_raw = taxonomy.get("internal_fraud_type_to_branch", {}) if isinstance(taxonomy, dict) else {}
    mapping: dict[str, str] = {}
    if isinstance(mapping_raw, dict):
        mapping = {
            str(key).strip(): str(value).strip()
            for key, value in mapping_raw.items()
            if str(key).strip() and str(value).strip()
        }
    branch_id = mapping.get(normalized, DEFAULT_FALLBACK_BRANCH_ID)
    labels = _branches_map(taxonomy)
    branch_label = labels.get(branch_id, branch_id)
    return {"id": branch_id, "label": branch_label}
