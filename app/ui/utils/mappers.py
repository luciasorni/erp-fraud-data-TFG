from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.erp_fraud.catalog.test_spec_loader import load_test_specs_from_catalog


MISSING_RUN_TEXT = "No disponible en este run"
NOT_GENERATED_TEXT = "No generado para este run"


@lru_cache(maxsize=1)
def _catalog_metadata_by_test_id() -> dict[str, dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    out: dict[str, dict[str, Any]] = {}
    for catalog_dir in (repo_root / "tests" / "catalog", repo_root / "tests" / "catalog_o2c"):
        if not catalog_dir.exists():
            continue
        for spec in load_test_specs_from_catalog(catalog_dir, validate_schema=False):
            if not isinstance(spec, dict):
                continue
            test_id = str(spec.get("test_id") or spec.get("id") or "").strip()
            if not test_id:
                continue
            out[test_id] = {
                "test_id": test_id,
                "fraud_type": _clean_text(spec.get("fraud_type")),
                "process_step": _clean_text(spec.get("process_step")),
                "name": _clean_text(spec.get("name")),
                "description": _clean_text(spec.get("description")),
            }
    return out


def catalog_test_metadata(test_id: str | None) -> dict[str, Any]:
    return _catalog_metadata_by_test_id().get(str(test_id or "").strip(), {})


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "-", "none", "null", "nan"}:
        return ""
    return text


def _first_text(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _text_or_missing(*values: Any, missing_text: str = MISSING_RUN_TEXT) -> str:
    text = _first_text(*values)
    return text or missing_text


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _attrs(item: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    value = item.get("attributes")
    return value if isinstance(value, dict) else {}


def _test_id_from_item(item: dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return ""
    return _first_text(item.get("test_id"), item.get("id"), item.get("title"), _attrs(item).get("test_id"))


def _index_by_test_id(items: List[Dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        test_id = _test_id_from_item(item)
        if test_id and test_id not in out:
            out[test_id] = item
    return out


def build_run_kpis(graph_payload: Dict[str, Any]) -> Dict[str, int]:
    counts = graph_payload.get("counts", {}) or {}
    return {
        "hypotheses": int(counts.get("hypotheses", 0) or 0),
        "selected_tests": int(counts.get("selected_tests", 0) or 0),
        "findings": int(counts.get("findings", 0) or 0),
        "scores": int(counts.get("scores", 0) or 0),
    }


def build_execution_metrics(runs: List[Dict[str, Any]]) -> Dict[str, int]:
    metrics = {"total": len(runs), "completed": 0, "running": 0, "failed": 0}
    for run in runs:
        status = str(run.get("status", "")).upper()
        if status == "COMPLETED":
            metrics["completed"] += 1
        elif status in {"RUNNING", "SUBMITTED"}:
            metrics["running"] += 1
        elif status == "FAILED":
            metrics["failed"] += 1
    return metrics


def extract_score_value(item: Dict[str, Any]) -> Optional[float]:
    attrs = item.get("attributes", {}) or {}
    confidence = attrs.get("confidence")
    if confidence is not None:
        try:
            return float(confidence)
        except (TypeError, ValueError):
            pass
    subtitle = str(item.get("subtitle", "")).strip()
    if subtitle.startswith("confidence="):
        try:
            return float(subtitle.split("=", 1)[1])
        except ValueError:
            return None
    return None


def findings_table_rows(
    findings: List[Dict[str, Any]],
    *,
    selected_tests: List[Dict[str, Any]] | None = None,
    explanations: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    rows = []
    selected_by_test = _index_by_test_id(selected_tests or [])
    explanations_by_test = _index_by_test_id(explanations or [])

    for index, item in enumerate(findings, start=1):
        attrs = _attrs(item)
        test_id = _test_id_from_item(item) or f"FIND-{index:03d}"
        selected_test = selected_by_test.get(test_id, {})
        selected_attrs = _attrs(selected_test)
        explanation = explanations_by_test.get(test_id, {})
        explanation_attrs = _attrs(explanation)
        catalog_meta = catalog_test_metadata(test_id)
        finding_count = _first_int(attrs.get("finding_count"), explanation_attrs.get("finding_count"), 0) or 0
        error_summary = _first_text(attrs.get("error_summary"), attrs.get("applicability_reason"))

        rows.append(
            {
                "finding_id": item.get("id") or f"FIND-{index:03d}",
                "title": item.get("title") or test_id or "Hallazgo",
                "summary": error_summary or item.get("summary") or "",
                "status": item.get("status") or "",
                "test_id": test_id,
                "fraud_type": _text_or_missing(
                    item.get("subtitle"),
                    attrs.get("fraud_type"),
                    explanation.get("subtitle"),
                    explanation_attrs.get("fraud_type"),
                    selected_attrs.get("fraud_type"),
                    catalog_meta.get("fraud_type"),
                ),
                "finding_count": finding_count,
                "finding_count_text": str(finding_count),
                "sample_entity_key": attrs.get("sample_entity_key"),
                "sample_keys": attrs.get("sample_keys", {}),
                "sample_query_id": attrs.get("sample_query_id"),
                "rows": attrs.get("rows", []),
                "columns": attrs.get("columns", []),
                "evidence_columns": attrs.get("evidence_columns", []),
                "required_keys": attrs.get("required_keys", []),
                "missing_keys": attrs.get("missing_keys", []),
                "drilldown_ready": attrs.get("drilldown_ready", False),
                "drilldown_error": attrs.get("drilldown_error"),
                "error_summary": error_summary or None,
                "process_step": _text_or_missing(
                    attrs.get("process_step"),
                    explanation_attrs.get("process_step"),
                    selected_attrs.get("process_step"),
                    catalog_meta.get("process_step"),
                ),
                "catalog_name": catalog_meta.get("name"),
                "hypothesis_id": _first_text(selected_attrs.get("hypothesis_id"), selected_test.get("subtitle")),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            not (bool(row.get("drilldown_ready")) or bool(row.get("rows"))),
            -(int(row.get("finding_count", 0) or 0)),
            str(row.get("test_id") or ""),
        ),
    )


def score_interpretation(score: Optional[float]) -> Dict[str, str]:
    if score is None:
        return {"label": "Sin score", "summary": "No hay score agregado disponible para este run."}
    if score >= 0.75:
        return {"label": "Señal alta", "summary": "La combinación de findings y scoring sitúa el caso en una prioridad alta de revisión."}
    if score >= 0.45:
        return {"label": "Señal media", "summary": "El caso presenta indicios consistentes, pero requiere contraste adicional antes de escalarlo."}
    return {"label": "Señal moderada", "summary": "El caso muestra indicios parciales; conviene interpretarlo junto con la evidencia y las recomendaciones."}


def report_findings_count(report_payload: Dict[str, Any]) -> Optional[int]:
    ranking = report_payload.get("ranking", {})
    if isinstance(ranking, dict):
        value = ranking.get("row_count")
        if value is not None:
            return int(value)
    return None


def explanation_rows(
    explanations: List[Dict[str, Any]],
    *,
    findings: List[Dict[str, Any]] | None = None,
    selected_tests: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    finding_rows = findings_table_rows(findings or [], selected_tests=selected_tests, explanations=[])
    findings_by_test = {row.get("test_id"): row for row in finding_rows if row.get("test_id")}
    selected_by_test = _index_by_test_id(selected_tests or [])
    rows: list[dict[str, Any]] = []

    for item in explanations or []:
        if not isinstance(item, dict):
            continue
        attrs = _attrs(item)
        test_id = _test_id_from_item(item)
        finding = findings_by_test.get(test_id, {})
        selected = selected_by_test.get(test_id, {})
        selected_attrs = _attrs(selected)
        catalog_meta = catalog_test_metadata(test_id)
        finding_count = _first_int(attrs.get("finding_count"), finding.get("finding_count"), 0)
        rows.append(
            {
                **item,
                "test_id": test_id,
                "fraud_type": _text_or_missing(
                    item.get("subtitle"),
                    item.get("fraud_type"),
                    attrs.get("fraud_type"),
                    finding.get("fraud_type"),
                    selected_attrs.get("fraud_type"),
                    catalog_meta.get("fraud_type"),
                ),
                "process_step": _text_or_missing(
                    attrs.get("process_step"),
                    finding.get("process_step"),
                    selected_attrs.get("process_step"),
                    catalog_meta.get("process_step"),
                ),
                "finding_count": finding_count,
                "finding_count_text": str(finding_count) if finding_count is not None else MISSING_RUN_TEXT,
                "status_detail": _first_text(finding.get("error_summary"), attrs.get("error_summary")),
            }
        )
    return rows


def explanation_for_test(
    explanations: List[Dict[str, Any]],
    test_id: Optional[str],
    *,
    findings: List[Dict[str, Any]] | None = None,
    selected_tests: List[Dict[str, Any]] | None = None,
) -> Optional[Dict[str, Any]]:
    if not test_id:
        return None
    enriched = explanation_rows(explanations, findings=findings, selected_tests=selected_tests)
    for item in enriched:
        if item.get("test_id") == test_id or _attrs(item).get("cited_test_id") == test_id:
            return item

    finding_rows = findings_table_rows(findings or [], selected_tests=selected_tests, explanations=[])
    finding = next((row for row in finding_rows if row.get("test_id") == test_id), None)
    selected = _index_by_test_id(selected_tests or []).get(test_id, {})
    selected_attrs = _attrs(selected)
    catalog_meta = catalog_test_metadata(test_id)
    if not finding and not selected and not catalog_meta:
        return explanations[0] if explanations else None

    summary = _first_text(
        finding.get("error_summary") if finding else None,
        selected.get("summary") if isinstance(selected, dict) else None,
        catalog_meta.get("description"),
        "No se generó explicación narrativa específica para este test en este run.",
    )
    return {
        "test_id": test_id,
        "title": test_id,
        "summary": summary,
        "fraud_type": _text_or_missing(
            finding.get("fraud_type") if finding else None,
            selected_attrs.get("fraud_type"),
            catalog_meta.get("fraud_type"),
        ),
        "process_step": _text_or_missing(
            finding.get("process_step") if finding else None,
            selected_attrs.get("process_step"),
            catalog_meta.get("process_step"),
        ),
        "finding_count": finding.get("finding_count") if finding else 0,
        "finding_count_text": str(finding.get("finding_count", 0)) if finding else "0",
        "referenced_columns": [],
        "cited_keys": {},
        "attributes": {
            "process_step": _text_or_missing(
                finding.get("process_step") if finding else None,
                selected_attrs.get("process_step"),
                catalog_meta.get("process_step"),
            )
        },
    }


def recommendations_for_finding(
    recommendations: List[Dict[str, Any]],
    *,
    finding: Dict[str, Any] | None = None,
    selected_tests: List[Dict[str, Any]] | None = None,
    explanations: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    selected_by_test = _index_by_test_id(selected_tests or [])
    explanations_by_test = {item.get("test_id"): item for item in explanation_rows(explanations or [], findings=[], selected_tests=selected_tests)}
    current_test_id = _test_id_from_item(finding or {})
    out: list[dict[str, Any]] = []

    def _mentions_current_test(item: dict[str, Any], attrs: dict[str, Any]) -> bool:
        if not current_test_id:
            return False
        values = [
            item.get("title"),
            item.get("summary"),
            item.get("subtitle"),
            item.get("test_id"),
            attrs.get("test_id"),
            attrs.get("why"),
            attrs.get("rationale"),
            attrs.get("procedure"),
            attrs.get("action"),
            attrs.get("evidence"),
        ]
        return any(current_test_id in str(value) for value in values if value is not None)

    for item in recommendations or []:
        if not isinstance(item, dict):
            continue
        attrs = _attrs(item)
        section = _first_text(attrs.get("section"), item.get("section"))
        copy = {**item, "attributes": dict(attrs)}

        if section == "recommended_tests" or str(item.get("status", "")).strip() == "recommended_test":
            test_id = _first_text(attrs.get("test_id"), item.get("title") if str(item.get("title", "")).startswith("TST-") else None, item.get("summary") if str(item.get("summary", "")).startswith("TST-") else None)
            selected = selected_by_test.get(test_id, {})
            selected_attrs = _attrs(selected)
            explanation = explanations_by_test.get(test_id, {})
            catalog_meta = catalog_test_metadata(test_id)
            rationale = _first_text(
                attrs.get("rationale"),
                attrs.get("why"),
                item.get("summary") if _clean_text(item.get("summary")) != test_id else None,
                selected.get("summary") if isinstance(selected, dict) else None,
                explanation.get("summary") if isinstance(explanation, dict) else None,
                catalog_meta.get("description"),
            )
            copy["title"] = test_id or item.get("title") or "Test recomendado"
            copy["summary"] = rationale or "El second-level no generó detalle adicional para este ítem."
            copy["subtitle"] = _first_text(
                selected_attrs.get("hypothesis_id"),
                selected_attrs.get("fraud_type"),
                catalog_meta.get("fraud_type"),
            ) or None
            copy["attributes"] = {
                **copy["attributes"],
                "test_id": test_id or None,
                "source": _first_text(selected.get("status"), selected.get("source")),
                "process_step": _text_or_missing(selected_attrs.get("process_step"), catalog_meta.get("process_step")),
                "relation_to_current_finding": (
                    "Corresponde al test del hallazgo actual."
                    if current_test_id and test_id == current_test_id
                    else "También forma parte de los tests seleccionados o sugeridos para ampliar contraste."
                ),
            }
        elif section == "recommendations" or str(item.get("status", "")).strip() == "recommended_action":
            if current_test_id and not _mentions_current_test(item, attrs):
                continue
            summary = _first_text(attrs.get("why"), item.get("summary"))
            copy["summary"] = summary or "Acción sugerida para reforzar la investigación del run."
        elif section == "audit_procedures" or str(item.get("status", "")).strip() == "audit_procedure":
            if current_test_id and not _mentions_current_test(item, attrs):
                continue
            summary = _first_text(attrs.get("why"), attrs.get("procedure"), item.get("summary"))
            copy["summary"] = summary or "No generado para este run."
        out.append(copy)

    return out


def comparison_insights_for_case(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in items if isinstance(item, dict)]


def split_recommendation_sections(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    sections = {
        "recommendations": [],
        "recommended_tests": [],
        "audit_procedures": [],
    }
    for item in items:
        status = str(item.get("status", "")).strip()
        if status == "recommended_action":
            sections["recommendations"].append(item)
        elif status == "recommended_test":
            sections["recommended_tests"].append(item)
        elif status == "audit_procedure":
            sections["audit_procedures"].append(item)
    return sections
