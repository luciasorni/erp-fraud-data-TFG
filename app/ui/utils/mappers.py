from __future__ import annotations

from typing import Any, Dict, List, Optional


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


def findings_table_rows(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for index, item in enumerate(findings, start=1):
        attrs = item.get("attributes", {}) or {}
        rows.append(
            {
                "finding_id": item.get("id") or f"FIND-{index:03d}",
                "title": item.get("title") or item.get("subtitle") or "Hallazgo",
                "summary": item.get("summary") or "",
                "status": item.get("status") or "",
                "test_id": item.get("id") or "",
                "fraud_type": item.get("subtitle") or "",
                "finding_count": attrs.get("finding_count", 0),
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
                "error_summary": attrs.get("error_summary"),
                "process_step": attrs.get("process_step"),
            }
        )
    return rows


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


def explanation_for_test(explanations: List[Dict[str, Any]], test_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not test_id:
        return None
    for item in explanations:
        if item.get("id") == test_id:
            return item
    return explanations[0] if explanations else None


def recommendations_for_finding(recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return recommendations


def comparison_insights_for_case(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return items


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
