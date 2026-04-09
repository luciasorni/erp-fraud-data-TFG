"""Alineación taxonómica O2C (RF11-12)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml


DEFAULT_MATRIX_PATH = "docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv"
DEFAULT_TAXONOMY_PATH = "config/fraud_tree_taxonomy.yaml"


def _load_yaml(path: str | Path) -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"No existe YAML: {cfg_path}")
    payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido (raíz no objeto): {cfg_path}")
    return payload


def _load_matrix_fraud_types(matrix_csv_path: str | Path) -> set[str]:
    matrix_path = Path(matrix_csv_path)
    if not matrix_path.exists():
        raise FileNotFoundError(f"No existe matriz O2C: {matrix_path}")
    out: set[str] = set()
    with matrix_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if "fraud_type" not in (reader.fieldnames or []):
            raise ValueError("Matriz O2C inválida: falta columna fraud_type")
        for row in reader:
            value = str(row.get("fraud_type", "")).strip()
            if value:
                out.add(value)
    return out


def validate_o2c_taxonomy_alignment(
    *,
    matrix_csv_path: str | Path = DEFAULT_MATRIX_PATH,
    taxonomy_config_path: str | Path = DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    taxonomy = _load_yaml(taxonomy_config_path)
    matrix_fraud_types = sorted(_load_matrix_fraud_types(matrix_csv_path))

    branches_raw = taxonomy.get("branches", []) if isinstance(taxonomy, dict) else []
    branch_ids: set[str] = set()
    if isinstance(branches_raw, list):
        for row in branches_raw:
            if isinstance(row, dict):
                bid = str(row.get("id", "")).strip()
                if bid:
                    branch_ids.add(bid)

    mapping_raw = taxonomy.get("internal_fraud_type_to_branch", {}) if isinstance(taxonomy, dict) else {}
    mapping: dict[str, str] = {}
    if isinstance(mapping_raw, dict):
        mapping = {
            str(key).strip(): str(value).strip()
            for key, value in mapping_raw.items()
            if str(key).strip() and str(value).strip()
        }

    errors: list[str] = []
    mapping_rows: list[dict[str, str]] = []
    for fraud_type in matrix_fraud_types:
        branch = mapping.get(fraud_type, "")
        if not branch:
            errors.append(f"fraud_type sin mapping en taxonomy: {fraud_type}")
            continue
        if branch not in branch_ids:
            errors.append(
                f"branch inexistente para fraud_type '{fraud_type}': {branch}"
            )
            continue
        mapping_rows.append({"fraud_type": fraud_type, "fraud_tree_branch": branch})

    status = "OK" if not errors else "ERROR"
    return {
        "status": status,
        "matrix_csv_path": str(Path(matrix_csv_path)),
        "taxonomy_config_path": str(Path(taxonomy_config_path)),
        "matrix_fraud_types": matrix_fraud_types,
        "mapped_rows": mapping_rows,
        "errors": errors,
    }
