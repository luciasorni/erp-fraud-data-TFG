"""Evaluadores automáticos RF14b (schema/allowlist, guardrails, KB citations)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..catalog import load_test_specs_from_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_project_path(path_value: str | Path) -> str:
    raw = str(path_value).strip()
    if not raw:
        return ""
    path = Path(raw)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())


def _catalog_allowlist_test_ids(catalog_path: str) -> set[str]:
    try:
        specs = load_test_specs_from_catalog(catalog_path=catalog_path, validate_schema=True)
    except Exception:
        return set()
    out: set[str] = set()
    for row in specs:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("id", "")).strip()
        if test_id:
            out.add(test_id)
    return out


def _check_schema_allowlist_compliance(state: Any) -> dict[str, Any]:
    metadata = getattr(state, "run_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    catalog_path = _resolve_project_path(str(metadata.get("catalog_path", "tests/catalog")).strip() or "tests/catalog")
    allowlist = _catalog_allowlist_test_ids(catalog_path)

    selected_tests = getattr(state, "selected_tests", [])
    findings = getattr(state, "findings", [])
    selected_ids = {
        str(row.get("test_id", "")).strip()
        for row in selected_tests
        if isinstance(row, dict) and str(row.get("test_id", "")).strip()
    }
    finding_ids = {
        str(row.get("test_id", "")).strip()
        for row in findings
        if isinstance(row, dict) and str(row.get("test_id", "")).strip()
    }

    errors: list[str] = []
    if allowlist:
        unknown_selected = sorted(selected_ids - allowlist)
        unknown_findings = sorted(finding_ids - allowlist)
        if unknown_selected:
            errors.append(f"selected_tests fuera de allowlist: {unknown_selected}")
        if unknown_findings:
            errors.append(f"findings fuera de allowlist: {unknown_findings}")
    return {
        "id": "schema_allowlist_compliance",
        "passed": len(errors) == 0,
        "errors": errors,
        "catalog_path": catalog_path,
        "allowlist_count": len(allowlist),
        "selected_tests_count": len(selected_ids),
        "findings_test_ids_count": len(finding_ids),
    }


def _build_finding_maps(findings: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    by_test: dict[str, dict[str, Any]] = {}
    by_test_entity: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        test_id = str(finding.get("test_id", "")).strip()
        if not test_id:
            continue
        by_test.setdefault(test_id, finding)
        rows = finding.get("rows", [])
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                entity_key = str(row.get("entity_key", "")).strip()
                if entity_key:
                    by_test_entity[(test_id, entity_key)] = row
    return by_test, by_test_entity


def _check_no_invented_columns(state: Any) -> dict[str, Any]:
    findings = [row for row in getattr(state, "findings", []) if isinstance(row, dict)]
    explanations = [row for row in getattr(state, "explanations", []) if isinstance(row, dict)]
    by_test, by_test_entity = _build_finding_maps(findings)

    errors: list[str] = []
    for idx, exp in enumerate(explanations):
        test_id = str(exp.get("test_id", "")).strip()
        cited_test_id = str(exp.get("cited_test_id", "")).strip()
        if not test_id:
            errors.append(f"explanations[{idx}]: test_id vacío")
            continue
        if cited_test_id and cited_test_id != test_id:
            errors.append(f"explanations[{idx}]: cited_test_id != test_id")
        finding = by_test.get(test_id)
        if finding is None:
            errors.append(f"explanations[{idx}]: test_id no existe en findings: {test_id}")
            continue

        finding_columns = {
            str(col).strip() for col in finding.get("columns", []) if str(col).strip()
        }
        referenced_columns = {
            str(col).strip() for col in exp.get("referenced_columns", []) if str(col).strip()
        }
        if finding_columns:
            unknown_ref = sorted(referenced_columns - finding_columns)
            if unknown_ref:
                errors.append(
                    f"explanations[{idx}]: referenced_columns fuera de result.columns: {unknown_ref}"
                )

        entity_key = str(exp.get("sample_entity_key", "")).strip()
        if entity_key:
            row = by_test_entity.get((test_id, entity_key))
            if row is not None:
                row_evidence = {
                    str(col).strip() for col in row.get("evidence_columns", []) if str(col).strip()
                }
                cited_evidence = {
                    str(col).strip()
                    for col in exp.get("cited_evidence_columns", [])
                    if str(col).strip()
                }
                unknown_evidence = sorted(cited_evidence - row_evidence)
                if unknown_evidence:
                    errors.append(
                        f"explanations[{idx}]: cited_evidence_columns fuera de row.evidence_columns: {unknown_evidence}"
                    )
    return {
        "id": "no_invented_columns_or_test_ids",
        "passed": len(errors) == 0,
        "errors": errors,
        "explanations_count": len(explanations),
    }


def _check_kb_citations_present(state: Any) -> dict[str, Any]:
    metadata = getattr(state, "run_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    kb_enabled = bool(metadata.get("explainer_kb_enabled", False))
    explanations = [row for row in getattr(state, "explanations", []) if isinstance(row, dict)]
    if not kb_enabled:
        return {
            "id": "kb_citations_present",
            "passed": True,
            "errors": [],
            "status": "SKIPPED_KB_DISABLED",
            "explanations_count": len(explanations),
        }

    errors: list[str] = []
    for idx, exp in enumerate(explanations):
        acfe_ref = exp.get("acfe_reference", {})
        if not isinstance(acfe_ref, dict):
            errors.append(f"explanations[{idx}]: acfe_reference inválido")
            continue
        hits = acfe_ref.get("hits", [])
        if not isinstance(hits, list) or len(hits) == 0:
            errors.append(f"explanations[{idx}]: sin hits KB")
    return {
        "id": "kb_citations_present",
        "passed": len(errors) == 0,
        "errors": errors,
        "status": "CHECKED_KB_ENABLED",
        "explanations_count": len(explanations),
    }


def evaluate_rf14b_automatic(state: Any) -> dict[str, Any]:
    checks = [
        _check_schema_allowlist_compliance(state),
        _check_no_invented_columns(state),
        _check_kb_citations_present(state),
    ]
    passed = all(bool(check.get("passed", False)) for check in checks)
    return {
        "version": "1.0.0",
        "passed": passed,
        "checks": checks,
        "checks_passed": sum(1 for check in checks if bool(check.get("passed", False))),
        "checks_total": len(checks),
    }
