from __future__ import annotations

import json
from typing import Any

from ..schemas.common import CountsSummary, UISectionItem
from ..schemas.results import GraphResultsResponse, ReportRanking, ReportResponse
from .aws_service import AWSAPISettings, create_s3_client, get_json_from_s3, get_s3_text, run_output_key, runs_prefix


def _bucket(settings: AWSAPISettings) -> str:
    return runs_prefix(settings=settings)[0]


def _read_json_artifact(
    *,
    run_id: str,
    relative_path: str,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
) -> Any:
    bucket = _bucket(settings)
    payload = get_s3_text(
        bucket=bucket,
        key=run_output_key(run_id=run_id, relative_path=relative_path, settings=settings),
        settings=settings,
        s3_client=s3_client,
    )
    if payload is None:
        return None
    return json.loads(payload)


def _looks_like_deterministic_summary(text: str) -> bool:
    lowered = str(text).strip().lower()
    if not lowered:
        return True
    markers = (
        "comparación rf16 completada",
        "comparacion rf16 completada",
        "base determinista",
        "tipologías comunes detectadas",
        "tipologias comunes detectadas",
        "fallback_mode=deterministic",
    )
    return any(marker in lowered for marker in markers)


def _synthesize_executive_summary(
    *,
    explanations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    scores: list[dict[str, Any]],
) -> str | None:
    narrative = None
    for item in explanations:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).strip().upper()
        summary = str(item.get("summary", "")).strip()
        if not summary or status in {"ERROR", "TIMEOUT"}:
            continue
        if "logs del runner" in summary.lower() or "error_summary" in summary.lower():
            continue
        narrative = item
        break
    top_finding = findings[0] if findings and isinstance(findings[0], dict) else {}
    top_score = scores[0] if scores and isinstance(scores[0], dict) else {}
    if narrative:
        test_id = str(narrative.get("test_id", "")).strip()
        fraud_type = str(narrative.get("fraud_type", "")).strip()
        summary = str(narrative.get("summary", "")).strip()
        finding_count = int(top_finding.get("finding_count", 0) or 0)
        confidence_text = ""
        try:
            confidence = top_score.get("confidence")
            if confidence is not None:
                confidence_text = f" El scoring agregado sitúa la señal en {float(confidence):.2f}."
        except (TypeError, ValueError):
            confidence_text = ""
        prefix = f"El análisis destaca {finding_count} hallazgos asociados al test {test_id}" if test_id else "El análisis destaca un conjunto de hallazgos relevantes"
        if fraud_type:
            prefix += f" para la tipología {fraud_type}"
        return f"{prefix}. {summary}{confidence_text}"
    if top_finding:
        test_id = str(top_finding.get("test_id", "")).strip()
        fraud_type = str(top_finding.get("fraud_type", "")).strip()
        finding_count = int(top_finding.get("finding_count", 0) or 0)
        return (
            f"El run prioriza {finding_count} hallazgos vinculados al test {test_id or 'principal'}"
            f"{f' y a la tipología {fraud_type}' if fraud_type else ''}. "
            "Conviene revisar la evidencia detallada y contrastarla con la documentación soporte."
        )
    return None


def _as_ui_item(*, raw: dict[str, Any], kind: str) -> UISectionItem:
    if kind == "hypothesis":
        return UISectionItem(
            id=str(raw.get("hypothesis_id", "")).strip() or None,
            title=str(raw.get("title", "")).strip() or None,
            subtitle=str(raw.get("fraud_type", "")).strip() or None,
            status=str(raw.get("source", "")).strip() or None,
            summary=str(raw.get("description", "")).strip() or None,
            attributes={
                "candidate_test_ids": list(raw.get("candidate_test_ids", [])),
                "process_step": raw.get("process_step"),
                "tool_context": raw.get("tool_context", {}),
            },
        )
    if kind == "selected_test":
        return UISectionItem(
            id=str(raw.get("test_id", "")).strip() or None,
            title=str(raw.get("test_id", "")).strip() or None,
            subtitle=str(raw.get("hypothesis_id", "")).strip() or None,
            status=str(raw.get("source", "")).strip() or None,
            summary=", ".join(str(x) for x in raw.get("match_reasons", []) if str(x).strip()) or None,
            attributes={
                "score": raw.get("score"),
                "match_reasons": list(raw.get("match_reasons", [])),
            },
        )
    if kind == "finding":
        rows = raw.get("rows", [])
        first_row = rows[0] if isinstance(rows, list) and rows else {}
        first_row = first_row if isinstance(first_row, dict) else {}
        metadata = raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {}
        return UISectionItem(
            id=str(raw.get("test_id", "")).strip() or None,
            title=str(raw.get("test_id", "")).strip() or None,
            subtitle=str(raw.get("fraud_type", "")).strip() or None,
            status=str(raw.get("status", "")).strip() or None,
            summary=f"{int(raw.get('finding_count', 0) or 0)} hallazgos detectados",
            attributes={
                "finding_count": int(raw.get("finding_count", 0) or 0),
                "columns": list(raw.get("columns", [])),
                "sample_entity_key": first_row.get("entity_key"),
                "sample_keys": first_row.get("keys", {}),
                "sample_drilldown_template": first_row.get("drilldown_template", {}),
                "error_summary": str(raw.get("error_summary", "")).strip() or None,
                "process_step": metadata.get("process_step"),
                "rows": [row for row in rows if isinstance(row, dict)],
            },
        )
    if kind == "score":
        confidence = raw.get("confidence")
        try:
            confidence_value = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_value = None
        return UISectionItem(
            id=str(raw.get("final_label", "")).strip() or None,
            title=str(raw.get("final_label", "")).strip() or None,
            subtitle=f"confidence={confidence_value}" if confidence_value is not None else None,
            status=str(raw.get("source", "")).strip() or None,
            summary=str(raw.get("evidence_summary", "")).strip() or None,
            attributes={
                "confidence": confidence_value,
                "fraud_type_distribution": raw.get("fraud_type_distribution", {}),
                "ranking_top": list(raw.get("ranking", []))[:5],
                "summary": raw.get("summary", {}),
            },
        )
    if kind == "explanation":
        status = str(raw.get("status", "")).strip().upper()
        summary = str(raw.get("summary", "")).strip()
        is_technical_error = status in {"ERROR", "TIMEOUT"} or "error_summary" in summary.lower() or "logs del runner" in summary.lower()
        return UISectionItem(
            id=str(raw.get("test_id", "")).strip() or None,
            title=str(raw.get("test_id", "")).strip() or None,
            subtitle=str(raw.get("fraud_type", "")).strip() or None,
            status=status or None,
            summary=summary or None,
            attributes={
                "cited_test_id": raw.get("cited_test_id"),
                "cited_keys": raw.get("cited_keys", {}),
                "referenced_columns": list(raw.get("referenced_columns", [])),
                "process_step": raw.get("process_step"),
                "technical_error": is_technical_error,
                "content_type": "technical_error" if is_technical_error else "narrative",
            },
        )
    return UISectionItem(
        id=str(raw.get("run_id", "")).strip() or None,
        title=str(raw.get("title", "")).strip() or None,
        subtitle=str(raw.get("status", "")).strip() or None,
        status=str(raw.get("status", "")).strip() or None,
        summary=str(raw.get("summary", "")).strip() or None,
        attributes=raw,
    )


def load_graph_results(
    *,
    run_id: str,
    status: str,
    scope: str | None,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
) -> GraphResultsResponse:
    client = s3_client or create_s3_client(settings=settings)
    graph_state = _read_json_artifact(run_id=run_id, relative_path="graph/graph_state.json", settings=settings, s3_client=client) or {}
    hypotheses = _read_json_artifact(run_id=run_id, relative_path="graph/hypotheses.json", settings=settings, s3_client=client) or []
    selected_tests = _read_json_artifact(run_id=run_id, relative_path="graph/selected_tests.json", settings=settings, s3_client=client) or []
    findings = _read_json_artifact(run_id=run_id, relative_path="graph/findings.json", settings=settings, s3_client=client) or []
    scores = _read_json_artifact(run_id=run_id, relative_path="graph/scores.json", settings=settings, s3_client=client) or []
    explanations = _read_json_artifact(run_id=run_id, relative_path="graph/explanations.json", settings=settings, s3_client=client) or []
    second_level = _read_json_artifact(
        run_id=run_id,
        relative_path="graph/second_level_analysis.json",
        settings=settings,
        s3_client=client,
    ) or {}

    run_metadata = graph_state.get("run_metadata", {}) if isinstance(graph_state, dict) else {}
    second_level_items = []
    comparison_items = []
    executive_summary = None
    if isinstance(second_level, dict):
        llm_insights = second_level.get("llm_insights", {}) if isinstance(second_level.get("llm_insights"), dict) else {}
        deterministic = second_level.get("deterministic_comparison", {}) if isinstance(second_level.get("deterministic_comparison"), dict) else {}
        executive_summary = str(llm_insights.get("executive_summary", "")).strip() or None
        next_actions = llm_insights.get("next_actions", [])
        recommended_tests = llm_insights.get("recommended_tests", [])
        audit_procedures = llm_insights.get("audit_procedures", [])
        cross_process = llm_insights.get("cross_process_conclusions", [])
        summary = deterministic.get("summary", {}) if isinstance(deterministic.get("summary"), dict) else {}
        runs_compared = deterministic.get("run_ids", []) if isinstance(deterministic.get("run_ids"), list) else []
        common_selected_tests = [str(item).strip() for item in summary.get("common_selected_tests", []) if str(item).strip()]
        common_fraud_types = [
            str(item).strip() for item in summary.get("common_fraud_types_with_findings", []) if str(item).strip()
        ]
        if isinstance(next_actions, list):
            for idx, item in enumerate(next_actions, start=1):
                text = str(item).strip()
                if not text:
                    continue
                second_level_items.append(
                    UISectionItem(
                        id=f"next-action-{idx}",
                        title="Recomendación",
                        subtitle="Siguiente paso sugerido por el second-level explainer",
                        status="recommended_action",
                        summary=text,
                        attributes={"source": "llm_insights.next_actions", "section": "recommendations"},
                    )
                )
        if isinstance(recommended_tests, list):
            for idx, item in enumerate(recommended_tests, start=1):
                text = str(item).strip()
                if not text:
                    continue
                second_level_items.append(
                    UISectionItem(
                        id=f"recommended-test-{idx}",
                        title="Test recomendado",
                        subtitle="Contraste adicional sugerido por el LLM",
                        status="recommended_test",
                        summary=text,
                        attributes={"source": "llm_insights.recommended_tests", "section": "recommended_tests"},
                    )
                )
        if isinstance(audit_procedures, list):
            for idx, item in enumerate(audit_procedures, start=1):
                text = str(item).strip()
                if not text:
                    continue
                second_level_items.append(
                    UISectionItem(
                        id=f"audit-procedure-{idx}",
                        title="Procedimiento auditor",
                        subtitle="Acción de validación sugerida",
                        status="audit_procedure",
                        summary=text,
                        attributes={"source": "llm_insights.audit_procedures", "section": "audit_procedures"},
                    )
                )
        if isinstance(cross_process, list):
            for idx, item in enumerate(cross_process, start=1):
                text = str(item).strip()
                if not text:
                    continue
                comparison_items.append(
                    UISectionItem(
                        id=f"cross-process-{idx}",
                        title="Desviación relevante",
                        subtitle="Comparativa contextual del caso",
                        status="comparison",
                        summary=text,
                        attributes={
                            "source": "llm_insights.cross_process_conclusions",
                            "runs_compared": runs_compared,
                            "common_selected_tests": common_selected_tests,
                            "common_fraud_types_with_findings": common_fraud_types,
                            "executive_summary": executive_summary,
                        },
                    )
                )
        if summary:
            comparison_items.append(
                UISectionItem(
                    id="deterministic-summary",
                    title="Base de comparación",
                    subtitle="Contexto objetivo usado para contrastar el caso",
                    status="comparison_summary",
                    summary="El caso se ha comparado contra otros runs y contra las señales repetidas en los tests y tipologías compartidas.",
                    attributes={
                        "runs_compared": runs_compared,
                        "common_selected_tests": common_selected_tests,
                        "common_fraud_types_with_findings": common_fraud_types,
                        "summary": summary,
                        "executive_summary": executive_summary,
                    },
                )
            )

    if _looks_like_deterministic_summary(executive_summary or ""):
        executive_summary = _synthesize_executive_summary(
            explanations=[item for item in explanations if isinstance(item, dict)],
            findings=[item for item in findings if isinstance(item, dict)],
            scores=[item for item in scores if isinstance(item, dict)],
        )

    return GraphResultsResponse(
        run_id=run_id,
        scope=scope or str(run_metadata.get("process_scope", "")).strip() or None,
        status=status,
        graph_status=str(run_metadata.get("graph_status", "")).strip() or None,
        kb_index_status=str(run_metadata.get("kb_index_status", "")).strip() or None,
        executive_summary=executive_summary,
        counts=CountsSummary(
            hypotheses=len(hypotheses) if isinstance(hypotheses, list) else 0,
            selected_tests=len(selected_tests) if isinstance(selected_tests, list) else 0,
            findings=len(findings) if isinstance(findings, list) else 0,
            scores=len(scores) if isinstance(scores, list) else 0,
            explanations=len(explanations) if isinstance(explanations, list) else 0,
            second_level_analysis=len(second_level_items),
        ),
        hypotheses=[_as_ui_item(raw=item, kind="hypothesis") for item in hypotheses if isinstance(item, dict)],
        selected_tests=[_as_ui_item(raw=item, kind="selected_test") for item in selected_tests if isinstance(item, dict)],
        findings=[_as_ui_item(raw=item, kind="finding") for item in findings if isinstance(item, dict)],
        scores=[_as_ui_item(raw=item, kind="score") for item in scores if isinstance(item, dict)],
        explanations=[_as_ui_item(raw=item, kind="explanation") for item in explanations if isinstance(item, dict)],
        second_level_analysis=second_level_items,
        comparison_insights=comparison_items,
    )


def load_report(
    *,
    run_id: str,
    status: str,
    scope: str | None,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
) -> ReportResponse:
    client = s3_client or create_s3_client(settings=settings)
    report = _read_json_artifact(run_id=run_id, relative_path="report.json", settings=settings, s3_client=client) or {}
    ranking_raw = report.get("ranking", {}) if isinstance(report, dict) else {}
    ranking = ReportRanking()
    if isinstance(ranking_raw, dict):
        rows = ranking_raw.get("rows", [])
        ranking = ReportRanking(
            row_count=int(ranking_raw.get("row_count", len(rows) if isinstance(rows, list) else 0) or 0),
            rows=rows if isinstance(rows, list) else [],
            top_k=ranking_raw.get("top_k") if ranking_raw.get("top_k") is None else int(ranking_raw.get("top_k")),
        )
    return ReportResponse(
        run_id=run_id,
        scope=scope,
        status=status,
        overall_status=str(report.get("summary", {}).get("overall_status", "")).strip() or None,
        summary=report.get("summary", {}) if isinstance(report, dict) else {},
        ranking=ranking,
        test_runs=list(report.get("test_runs", [])) if isinstance(report, dict) else [],
        artifact_paths=report.get("artifact_paths", {}) if isinstance(report, dict) else {},
        metadata=report.get("metadata", {}) if isinstance(report, dict) else {},
    )
