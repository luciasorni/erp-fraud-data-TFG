"""Validación de matriz O2C hipótesis->tests->evidencias (RF11-11)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..catalog.test_spec_loader import load_test_specs_from_catalog

REQUIRED_COLUMNS = (
    "hypothesis_id",
    "hypothesis_title",
    "process_step",
    "fraud_type",
    "test_id",
    "test_status",
    "evidence_entity",
    "evidence_columns",
    "business_key_fields",
    "source_deviation_id",
    "notes",
)

ALLOWED_PROCESS_STEPS = {"sales_order", "delivery", "invoice", "collection"}
ALLOWED_TEST_STATUS = {"planned", "implemented", "deprecated"}


@dataclass(frozen=True)
class O2CMatrixValidationResult:
    status: str
    rows_total: int
    rows_valid: int
    errors: list[str]


def _load_yaml(path: str | Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyYAML no disponible") from exc
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"No existe YAML: {cfg_path}")
    payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido (raíz no objeto): {cfg_path}")
    return payload


def _split_semicolon_list(value: str) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def _build_allowed_fields_by_entity(canonical_schema_cfg: dict[str, Any]) -> dict[str, set[str]]:
    entities = canonical_schema_cfg.get("entities", {})
    if not isinstance(entities, dict):
        return {}
    out: dict[str, set[str]] = {}
    for entity_name, entity_cfg in entities.items():
        if not isinstance(entity_cfg, dict):
            continue
        fields: set[str] = set()
        for key in ("required_fields", "optional_fields"):
            rows = entity_cfg.get(key, [])
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        name = str(row.get("name", "")).strip()
                        if name:
                            fields.add(name)
        out[str(entity_name)] = fields
    return out


def _build_business_key_fields_by_entity(identity_cfg: dict[str, Any]) -> dict[str, set[str]]:
    entities = identity_cfg.get("entities", {})
    if not isinstance(entities, dict):
        return {}
    out: dict[str, set[str]] = {}
    for entity_name, entity_cfg in entities.items():
        if not isinstance(entity_cfg, dict):
            continue
        business_key = entity_cfg.get("business_key", {})
        if not isinstance(business_key, dict):
            continue
        fields = business_key.get("key_fields", [])
        if isinstance(fields, list):
            out[str(entity_name)] = {str(f).strip() for f in fields if str(f).strip()}
    return out


def validate_o2c_hypothesis_matrix(
    *,
    matrix_csv_path: str | Path = "docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv",
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
    identity_config_path: str | Path = "config/o2c_entity_identity.yaml",
    o2c_catalog_path: str | Path = "tests/catalog_o2c",
) -> dict[str, Any]:
    matrix_path = Path(matrix_csv_path)
    if not matrix_path.exists():
        raise FileNotFoundError(f"No existe matriz O2C: {matrix_path}")

    canonical_cfg = _load_yaml(canonical_schema_config_path)
    identity_cfg = _load_yaml(identity_config_path)
    allowed_fields_by_entity = _build_allowed_fields_by_entity(canonical_cfg)
    allowed_entities = set(allowed_fields_by_entity.keys())
    key_fields_by_entity = _build_business_key_fields_by_entity(identity_cfg)
    catalog_specs = load_test_specs_from_catalog(o2c_catalog_path, validate_schema=True)
    catalog_by_test_id: dict[str, dict[str, Any]] = {}
    for spec in catalog_specs:
        test_id = str(spec.get("id", "")).strip()
        if test_id:
            catalog_by_test_id[test_id] = spec

    errors: list[str] = []
    rows_total = 0
    rows_valid = 0
    seen_keys: set[tuple[str, str]] = set()

    with matrix_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = tuple(reader.fieldnames or [])
        missing_headers = [col for col in REQUIRED_COLUMNS if col not in headers]
        if missing_headers:
            errors.append(f"Missing required CSV headers: {', '.join(missing_headers)}")
        for idx, row in enumerate(reader, start=2):
            rows_total += 1
            hypothesis_id = str(row.get("hypothesis_id", "")).strip()
            process_step = str(row.get("process_step", "")).strip()
            fraud_type = str(row.get("fraud_type", "")).strip()
            test_id = str(row.get("test_id", "")).strip()
            test_status = str(row.get("test_status", "")).strip().lower()
            evidence_entity = str(row.get("evidence_entity", "")).strip()
            evidence_columns = _split_semicolon_list(str(row.get("evidence_columns", "")))
            business_key_fields = _split_semicolon_list(str(row.get("business_key_fields", "")))
            source_deviation_id = str(row.get("source_deviation_id", "")).strip()

            row_errors: list[str] = []
            if not hypothesis_id:
                row_errors.append("hypothesis_id vacío")
            if not process_step:
                row_errors.append("process_step vacío")
            elif process_step not in ALLOWED_PROCESS_STEPS:
                row_errors.append(f"process_step inválido: {process_step}")
            if not fraud_type:
                row_errors.append("fraud_type vacío")
            if not test_id:
                row_errors.append("test_id vacío")
            elif not test_id.startswith("TST-O2C-"):
                row_errors.append(f"test_id debe empezar por TST-O2C-: {test_id}")
            elif test_status == "implemented":
                spec = catalog_by_test_id.get(test_id)
                if spec is None:
                    row_errors.append(f"test_id implementado no existe en catálogo O2C: {test_id}")
                else:
                    spec_fraud_type = str(spec.get("fraud_type", "")).strip()
                    spec_process_step = str(spec.get("process_step", "")).strip()
                    if spec_fraud_type and fraud_type != spec_fraud_type:
                        row_errors.append(
                            f"fraud_type no coincide con catálogo para {test_id}: "
                            f"matrix={fraud_type}, catalog={spec_fraud_type}"
                        )
                    if spec_process_step and process_step != spec_process_step:
                        row_errors.append(
                            f"process_step no coincide con catálogo para {test_id}: "
                            f"matrix={process_step}, catalog={spec_process_step}"
                        )
            if test_status not in ALLOWED_TEST_STATUS:
                row_errors.append(f"test_status inválido: {test_status}")
            if not source_deviation_id.startswith("O2C-"):
                row_errors.append(f"source_deviation_id inválido: {source_deviation_id}")

            if evidence_entity not in allowed_entities:
                row_errors.append(f"evidence_entity inválida: {evidence_entity}")
            else:
                allowed_fields = allowed_fields_by_entity.get(evidence_entity, set())
                unknown_evidence = [col for col in evidence_columns if col not in allowed_fields]
                if unknown_evidence:
                    row_errors.append(
                        f"evidence_columns fuera de schema ({evidence_entity}): {', '.join(unknown_evidence)}"
                    )
                allowed_keys = key_fields_by_entity.get(evidence_entity, set())
                unknown_keys = [col for col in business_key_fields if col not in allowed_keys]
                if unknown_keys:
                    row_errors.append(
                        f"business_key_fields fuera de identity config ({evidence_entity}): {', '.join(unknown_keys)}"
                    )

            uniqueness_key = (hypothesis_id, test_id)
            if uniqueness_key in seen_keys:
                row_errors.append(f"duplicado hypothesis_id+test_id: {hypothesis_id} + {test_id}")
            else:
                seen_keys.add(uniqueness_key)

            if row_errors:
                errors.append(f"row {idx}: " + " | ".join(row_errors))
            else:
                rows_valid += 1

    status = "OK" if not errors else "ERROR"
    return {
        "status": status,
        "rows_total": rows_total,
        "rows_valid": rows_valid,
        "errors": errors,
        "matrix_csv_path": str(matrix_path),
        "canonical_schema_config_path": str(canonical_schema_config_path),
        "identity_config_path": str(identity_config_path),
        "o2c_catalog_path": str(o2c_catalog_path),
    }
