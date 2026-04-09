"""Validación de matriz P2P hipótesis->tests->evidencias."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..catalog.drilldown_keys import get_drilldown_min_keys_by_test_id
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

ALLOWED_PROCESS_STEPS = {"invoice_posting", "goods_receipt"}
ALLOWED_TEST_STATUS = {"implemented", "planned", "deprecated"}
ALLOWED_EVIDENCE_ENTITY = {"fraud_1"}


def _split_semicolon_list(value: str) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def _build_catalog_index(catalog_path: str | Path) -> dict[str, dict[str, Any]]:
    specs = load_test_specs_from_catalog(catalog_path, validate_schema=True)
    out: dict[str, dict[str, Any]] = {}
    for row in specs:
        test_id = str(row.get("id", "")).strip()
        if test_id:
            out[test_id] = row
    return out


def validate_p2p_hypothesis_matrix(
    *,
    matrix_csv_path: str | Path = "docs/p2p/artifacts/rf13_p2p_hypothesis_matrix.csv",
    catalog_path: str | Path = "tests/catalog",
) -> dict[str, Any]:
    matrix_path = Path(matrix_csv_path)
    if not matrix_path.exists():
        raise FileNotFoundError(f"No existe matriz P2P: {matrix_path}")

    catalog_by_test_id = _build_catalog_index(catalog_path)
    min_keys_map = get_drilldown_min_keys_by_test_id()

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
            if process_step not in ALLOWED_PROCESS_STEPS:
                row_errors.append(f"process_step inválido: {process_step}")
            if not test_id:
                row_errors.append("test_id vacío")
            elif test_id not in catalog_by_test_id:
                row_errors.append(f"test_id no existe en catálogo: {test_id}")

            if test_status not in ALLOWED_TEST_STATUS:
                row_errors.append(f"test_status inválido: {test_status}")
            if evidence_entity not in ALLOWED_EVIDENCE_ENTITY:
                row_errors.append(f"evidence_entity inválida: {evidence_entity}")
            if not source_deviation_id.startswith("P2P-"):
                row_errors.append(f"source_deviation_id inválido: {source_deviation_id}")

            spec = catalog_by_test_id.get(test_id, {})
            if spec:
                expected_fraud_type = str(spec.get("fraud_type", "")).strip()
                if expected_fraud_type and fraud_type != expected_fraud_type:
                    row_errors.append(
                        f"fraud_type no coincide con catálogo ({test_id}): {fraud_type} != {expected_fraud_type}"
                    )

                allowed_evidence = {
                    str(col).strip()
                    for col in (spec.get("evidence_columns", []) or [])
                    if str(col).strip()
                }
                unknown_evidence = [col for col in evidence_columns if col not in allowed_evidence]
                if unknown_evidence:
                    row_errors.append(
                        f"evidence_columns fuera de catálogo ({test_id}): {', '.join(unknown_evidence)}"
                    )

                min_keys = set(min_keys_map.get(test_id, ()))
                unknown_keys = [col for col in business_key_fields if col not in min_keys]
                if unknown_keys:
                    row_errors.append(
                        f"business_key_fields fuera de drilldown keys ({test_id}): {', '.join(unknown_keys)}"
                    )

            uniq = (hypothesis_id, test_id)
            if uniq in seen_keys:
                row_errors.append(f"duplicado hypothesis_id+test_id: {hypothesis_id} + {test_id}")
            else:
                seen_keys.add(uniq)

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
        "catalog_path": str(catalog_path),
    }

