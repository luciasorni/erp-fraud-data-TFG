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
        return UISectionItem(
            id=str(raw.get("test_id", "")).strip() or None,
            title=str(raw.get("test_id", "")).strip() or None,
            subtitle=str(raw.get("fraud_type", "")).strip() or None,
            status=str(raw.get("status", "")).strip() or None,
            summary=f"{int(raw.get('finding_count', 0) or 0)} findings",
            attributes={
                "finding_count": int(raw.get("finding_count", 0) or 0),
                "columns": list(raw.get("columns", [])),
                "sample_entity_key": first_row.get("entity_key"),
                "sample_keys": first_row.get("keys", {}),
                "sample_drilldown_template": first_row.get("drilldown_template", {}),
            },
        )
    if kind == "score":
        return UISectionItem(
            id=str(raw.get("final_label", "")).strip() or None,
            title=str(raw.get("final_label", "")).strip() or None,
            subtitle=f"confidence={raw.get('confidence')}",
            status=str(raw.get("source", "")).strip() or None,
            summary=str(raw.get("evidence_summary", "")).strip() or None,
            attributes={
                "fraud_type_distribution": raw.get("fraud_type_distribution", {}),
                "ranking_top": list(raw.get("ranking", []))[:5],
                "summary": raw.get("summary", {}),
            },
        )
    if kind == "explanation":
        return UISectionItem(
            id=str(raw.get("test_id", "")).strip() or None,
            title=str(raw.get("test_id", "")).strip() or None,
            subtitle=str(raw.get("fraud_type", "")).strip() or None,
            status=str(raw.get("status", "")).strip() or None,
            summary=str(raw.get("summary", "")).strip() or None,
            attributes={
                "cited_test_id": raw.get("cited_test_id"),
                "cited_keys": raw.get("cited_keys", {}),
                "referenced_columns": list(raw.get("referenced_columns", [])),
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
    if isinstance(second_level, dict):
        recommendations = second_level.get("recommendations", [])
        if isinstance(recommendations, list):
            for idx, item in enumerate(recommendations, start=1):
                if not isinstance(item, dict):
                    continue
                second_level_items.append(
                    UISectionItem(
                        id=f"recommendation-{idx}",
                        title=str(item.get("title", "")).strip() or f"Recommendation {idx}",
                        subtitle=str(item.get("category", "")).strip() or None,
                        status=str(item.get("priority", "")).strip() or None,
                        summary=str(item.get("summary", "")).strip() or None,
                        attributes=item,
                    )
                )

    return GraphResultsResponse(
        run_id=run_id,
        scope=scope or str(run_metadata.get("process_scope", "")).strip() or None,
        status=status,
        graph_status=str(run_metadata.get("graph_status", "")).strip() or None,
        kb_index_status=str(run_metadata.get("kb_index_status", "")).strip() or None,
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
