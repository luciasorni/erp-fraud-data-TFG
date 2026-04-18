from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from ..schemas.common import CountsSummary, UISectionItem
from ..schemas.results import GraphResultsResponse, ReportRanking, ReportResponse
from .aws_service import AWSAPISettings, create_s3_client, get_json_from_s3, get_s3_text, list_s3_common_prefixes, run_output_key, runs_prefix
from src.erp_fraud.catalog.drilldown_keys import get_minimum_keys_for_test_id, get_missing_or_empty_minimum_keys_for_test_id, normalize_drilldown_keys
from src.erp_fraud.catalog.drilldown_templates import get_drilldown_query_id_for_test_id
from src.erp_fraud.catalog.test_spec_loader import load_test_specs_from_catalog
from src.erp_fraud.storage.runs_comparison import RunSnapshot, compare_run_snapshots


_RUN_ID_TIMESTAMP_RE = re.compile(r"(\d{8}-\d{6})$")


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
                "name": str(spec.get("name", "")).strip() or None,
                "fraud_type": str(spec.get("fraud_type", "")).strip() or None,
                "process_step": str(spec.get("process_step", "")).strip() or None,
                "description": str(spec.get("description", "")).strip() or None,
                "red_flag_id": str(spec.get("red_flag_id", "")).strip() or None,
            }
    return out


def _catalog_metadata_for_test_id(test_id: str) -> dict[str, Any]:
    return _catalog_metadata_by_test_id().get(str(test_id or "").strip(), {})


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
    if isinstance(text, dict):
        return False
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


def _parse_structured(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[:1] not in {"{", "["}:
        return value
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            continue
    return value


def _risk_posture_from_scores(scores: list[dict[str, Any]]) -> str:
    top_score = scores[0] if scores and isinstance(scores[0], dict) else {}
    try:
        confidence = float(top_score.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence >= 0.75:
        return "Alto"
    if confidence >= 0.45:
        return "Medio"
    return "Moderado"


def _synthesize_executive_summary(
    *,
    explanations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    scores: list[dict[str, Any]],
) -> dict[str, Any] | None:
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
        return {
            "overall_assessment": f"{prefix}. {summary}{confidence_text}",
            "risk_posture": _risk_posture_from_scores(scores),
            "key_observations": [
                f"Hallazgos priorizados: {finding_count}.",
                f"Tipología principal: {fraud_type or 'no especificada'}.",
            ],
        }
    if top_finding:
        test_id = str(top_finding.get("test_id", "")).strip()
        fraud_type = str(top_finding.get("fraud_type", "")).strip()
        finding_count = int(top_finding.get("finding_count", 0) or 0)
        return {
            "overall_assessment": (
                f"El run prioriza {finding_count} hallazgos vinculados al test {test_id or 'principal'}"
                f"{f' y a la tipología {fraud_type}' if fraud_type else ''}. "
                "Conviene revisar la evidencia detallada y contrastarla con la documentación soporte."
            ),
            "risk_posture": _risk_posture_from_scores(scores),
            "key_observations": [
                f"Test priorizado: {test_id or 'principal'}.",
                f"Hallazgos detectados: {finding_count}.",
            ],
        }
    return None


def _normalize_executive_summary(value: Any) -> Any:
    parsed = _parse_structured(value)
    if isinstance(parsed, dict):
        overall = str(
            parsed.get("overall_assessment")
            or parsed.get("summary")
            or parsed.get("executive_summary")
            or ""
        ).strip()
        risk_posture = str(parsed.get("risk_posture") or "").strip()
        observations = parsed.get("key_observations")
        if not isinstance(observations, list):
            observations = parsed.get("key_evidence")
        key_observations = [str(item).strip() for item in (observations or []) if str(item).strip()]
        out = {}
        if overall:
            out["overall_assessment"] = overall
        if risk_posture:
            out["risk_posture"] = risk_posture
        if key_observations:
            out["key_observations"] = key_observations[:6]
        return out or None
    text = str(parsed or "").strip()
    return text or None


def _ui_item_from_normalized_item(*, raw: dict[str, Any], prefix: str, idx: int) -> UISectionItem | None:
    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    if not title and not summary:
        return None
    section = str(raw.get("section") or "").strip()
    if re.fullmatch(r"(Recomendación|Test recomendado|Procedimiento auditor)\s+\d+", title, flags=re.IGNORECASE):
        if section == "recommended_tests":
            explicit_test = str(raw.get("test_id") or raw.get("expected_value") or summary).strip()
            if explicit_test:
                title = explicit_test
        elif section == "recommendations" and summary:
            title = summary.split(".")[0].strip()[:110] or title
        elif section == "audit_procedures":
            explicit_procedure = str(raw.get("procedure") or summary).strip()
            if explicit_procedure:
                title = explicit_procedure.split(".")[0].strip()[:110] or title
        elif summary:
            title = summary.split(".")[0].strip()[:110] or title
    return UISectionItem(
        id=f"{prefix}-{idx}",
        title=title or prefix.title(),
        subtitle=str(raw.get("subtitle") or "").strip() or None,
        status=str(raw.get("status") or "").strip() or None,
        summary=summary or None,
        attributes={
            "section": section or None,
            "recommendation": raw.get("recommendation"),
            "procedure": raw.get("procedure"),
            "implication": raw.get("implication"),
            "evidence": raw.get("evidence", []),
            "owner": raw.get("owner"),
            "urgency": raw.get("urgency"),
            "priority": raw.get("priority"),
            "expected_value": raw.get("expected_value"),
            **(raw.get("attributes", {}) if isinstance(raw.get("attributes"), dict) else {}),
        },
    )


def _run_id_sort_key(run_id: str) -> tuple[datetime, str]:
    match = _RUN_ID_TIMESTAMP_RE.search(str(run_id).strip())
    if match:
        try:
            return (
                datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc),
                run_id,
            )
        except ValueError:
            pass
    return (datetime.min.replace(tzinfo=timezone.utc), run_id)


def _load_s3_snapshot(
    *,
    run_id: str,
    settings: AWSAPISettings,
    s3_client: Any,
) -> RunSnapshot | None:
    graph_state = _read_json_artifact(run_id=run_id, relative_path="graph/graph_state.json", settings=settings, s3_client=s3_client) or {}
    if not graph_state:
        return None
    selected_tests = _read_json_artifact(run_id=run_id, relative_path="graph/selected_tests.json", settings=settings, s3_client=s3_client) or []
    findings = _read_json_artifact(run_id=run_id, relative_path="graph/findings.json", settings=settings, s3_client=s3_client) or []
    scores = _read_json_artifact(run_id=run_id, relative_path="graph/scores.json", settings=settings, s3_client=s3_client) or []
    hypotheses = _read_json_artifact(run_id=run_id, relative_path="graph/hypotheses.json", settings=settings, s3_client=s3_client) or []
    report_payload = _read_json_artifact(run_id=run_id, relative_path="report.json", settings=settings, s3_client=s3_client) or {}
    run_metadata_payload = _read_json_artifact(run_id=run_id, relative_path="run_metadata.json", settings=settings, s3_client=s3_client) or {}
    api_request = _read_json_artifact(run_id=run_id, relative_path="api_request.json", settings=settings, s3_client=s3_client) or {}
    graph_meta = graph_state.get("run_metadata", {}) if isinstance(graph_state, dict) else {}
    report_summary = report_payload.get("summary", {}) if isinstance(report_payload, dict) else {}
    report_metadata_extra = ((report_payload.get("metadata") or {}).get("metadata_extra") or {}) if isinstance(report_payload, dict) else {}
    score_item = scores[0] if isinstance(scores, list) and scores and isinstance(scores[0], dict) else {}

    selected_test_ids: list[str] = []
    for row in selected_tests if isinstance(selected_tests, list) else []:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id", "")).strip()
        if test_id and test_id not in selected_test_ids:
            selected_test_ids.append(test_id)

    tests_with_findings: list[str] = []
    fraud_types_with_findings: dict[str, int] = {}
    findings_total = 0
    for row in findings if isinstance(findings, list) else []:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id", "")).strip()
        fraud_type = str(row.get("fraud_type", "")).strip()
        finding_count = int(row.get("finding_count", 0) or 0)
        findings_total += finding_count
        if finding_count > 0 and test_id and test_id not in tests_with_findings:
            tests_with_findings.append(test_id)
        if finding_count > 0 and fraud_type:
            fraud_types_with_findings[fraud_type] = fraud_types_with_findings.get(fraud_type, 0) + finding_count

    return RunSnapshot(
        run_id=run_id,
        run_dir=None,  # type: ignore[arg-type]
        dataset_id=str(api_request.get("dataset_id", "")).strip(),
        dataset_hash=str(graph_meta.get("dataset_hash", "")).strip() or str(run_metadata_payload.get("dataset_hash", "")).strip(),
        process_family=str(graph_meta.get("process_family", "")).strip()
        or str(run_metadata_payload.get("process_family", "")).strip()
        or str(report_metadata_extra.get("process_family", "")).strip()
        or "p2p",
        llm_mode=str(graph_meta.get("llm_mode", "")).strip() or str(api_request.get("llm_mode", "")).strip(),
        graph_status=str(graph_meta.get("graph_status", "")).strip(),
        overall_status=str(report_summary.get("overall_status", "")).strip(),
        selected_test_ids=selected_test_ids,
        selected_tests_count=len(selected_test_ids),
        findings_total=findings_total or int(report_summary.get("findings_total", 0) or 0),
        tests_with_findings=sorted(tests_with_findings),
        fraud_types_with_findings=dict(sorted(fraud_types_with_findings.items())),
        hypotheses_count=len([row for row in hypotheses if isinstance(row, dict)]),
        final_label=str(score_item.get("final_label", "")).strip(),
        confidence=float(score_item.get("confidence", 0.0) or 0.0),
        langsmith_trace_link=str(graph_meta.get("langsmith_trace_link", "")).strip(),
        generated_at_utc=str(graph_meta.get("updated_at_utc", "")).strip() or str(report_payload.get("generated_at_utc", "")).strip(),
    )


def _build_related_comparison_payload(
    *,
    run_id: str,
    scope: str | None,
    settings: AWSAPISettings,
    s3_client: Any,
) -> dict[str, Any] | None:
    current = _load_s3_snapshot(run_id=run_id, settings=settings, s3_client=s3_client)
    if current is None:
        return None
    current_api_request = _read_json_artifact(run_id=run_id, relative_path="api_request.json", settings=settings, s3_client=s3_client) or {}
    peers: list[RunSnapshot] = []
    seen = {run_id}

    peer_run_ids = [
        str(item).strip()
        for item in current_api_request.get("peer_run_ids", [])
        if str(item).strip() and str(item).strip() not in seen
    ] if isinstance(current_api_request.get("peer_run_ids"), list) else []
    for peer_id in peer_run_ids:
        snap = _load_s3_snapshot(run_id=peer_id, settings=settings, s3_client=s3_client)
        if snap is not None:
            peers.append(snap)
            seen.add(peer_id)

    bucket, prefix = runs_prefix(settings=settings)
    try:
        prefixes = list_s3_common_prefixes(bucket=bucket, prefix=prefix, settings=settings, s3_client=s3_client)
    except Exception:
        return compare_run_snapshots(snapshots=[current, *peers]) if peers else compare_run_snapshots(snapshots=[current])
    candidate_run_ids = sorted(
        [item.rstrip("/").split("/")[-1] for item in prefixes if item.rstrip("/").split("/")[-1]],
        key=_run_id_sort_key,
        reverse=True,
    )[:25]

    for candidate_run_id in candidate_run_ids:
        if candidate_run_id in seen:
            continue
        snap = _load_s3_snapshot(run_id=candidate_run_id, settings=settings, s3_client=s3_client)
        if snap is None:
            continue
        same_dataset = bool(current.dataset_id and snap.dataset_id == current.dataset_id)
        same_hash = bool(current.dataset_hash and snap.dataset_hash == current.dataset_hash)
        if not (same_dataset or same_hash):
            continue
        if snap.process_family == current.process_family:
            peers.append(snap)
            seen.add(candidate_run_id)
            if len([row for row in peers if row.process_family == current.process_family]) >= 3:
                continue
        elif len([row for row in peers if row.process_family != current.process_family]) < 2:
            peers.append(snap)
            seen.add(candidate_run_id)

    if not peers:
        return compare_run_snapshots(snapshots=[current])
    return compare_run_snapshots(snapshots=[current, *peers])


def _merge_comparison_source_items(
    *,
    llm_items: list[dict[str, Any]],
    deterministic_items: list[dict[str, Any]],
    related_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    section_order = ("intra_run", "historical", "cross_process")

    def _section_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for item in rows:
            if not isinstance(item, dict):
                continue
            section = str(item.get("section") or "").strip()
            if section:
                out[section] = item
        return out

    llm_map = _section_map(llm_items)
    deterministic_map = _section_map(deterministic_items)
    related_map = _section_map(related_items)

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for section in section_order:
        item = related_map.get(section) or llm_map.get(section) or deterministic_map.get(section)
        if not item:
            continue
        merged.append(item)
        item_id = str(item.get("id") or "").strip()
        if item_id:
            seen_ids.add(item_id)

    for source in (llm_items, deterministic_items, related_items):
        for item in source:
            if not isinstance(item, dict):
                continue
            section = str(item.get("section") or "").strip()
            if section in section_order:
                continue
            item_id = str(item.get("id") or "").strip()
            if item_id and item_id in seen_ids:
                continue
            merged.append(item)
            if item_id:
                seen_ids.add(item_id)

    return merged


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
        test_id = str(raw.get("test_id", "")).strip()
        catalog_meta = _catalog_metadata_for_test_id(test_id)
        return UISectionItem(
            id=test_id or None,
            title=test_id or None,
            subtitle=str(raw.get("hypothesis_id", "")).strip() or None,
            status=str(raw.get("source", "")).strip() or None,
            summary=", ".join(str(x) for x in raw.get("match_reasons", []) if str(x).strip()) or catalog_meta.get("description"),
            attributes={
                "hypothesis_id": str(raw.get("hypothesis_id", "")).strip() or None,
                "score": raw.get("score"),
                "match_reasons": list(raw.get("match_reasons", [])),
                "fraud_type": catalog_meta.get("fraud_type"),
                "process_step": catalog_meta.get("process_step"),
                "catalog_name": catalog_meta.get("name"),
                "catalog_description": catalog_meta.get("description"),
            },
        )
    if kind == "finding":
        rows = raw.get("rows", [])
        first_row = rows[0] if isinstance(rows, list) and rows else {}
        first_row = first_row if isinstance(first_row, dict) else {}
        metadata = raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {}
        test_id = str(raw.get("test_id", "")).strip()
        catalog_meta = _catalog_metadata_for_test_id(test_id)
        evidence_columns = list(raw.get("columns", []))

        def _normalize_finding_row(row: dict[str, Any]) -> dict[str, Any]:
            row_keys = row.get("keys", {}) if isinstance(row.get("keys"), dict) else {}
            template = row.get("drilldown_template", {}) if isinstance(row.get("drilldown_template"), dict) else {}
            template_params = template.get("params", {}) if isinstance(template.get("params"), dict) else {}
            merged_keys = normalize_drilldown_keys({**template_params, **row_keys})
            query_id = str(template.get("query_id", "")).strip()
            required_keys: list[str] = []
            missing_keys: list[str] = []
            ready = False
            error = None
            try:
                required_keys = list(get_minimum_keys_for_test_id(test_id))
                missing_keys = get_missing_or_empty_minimum_keys_for_test_id(test_id, merged_keys)
                query_id = query_id or get_drilldown_query_id_for_test_id(test_id)
                ready = not missing_keys
                if missing_keys:
                    error = f"Faltan keys mínimas para {test_id}: {missing_keys}"
            except (ValueError, KeyError) as exc:
                error = str(exc)
            return {
                **row,
                "keys": merged_keys,
                "query_id": query_id or None,
                "required_keys": required_keys,
                "missing_keys": missing_keys,
                "drilldown_ready": ready,
                "drilldown_error": error,
                "evidence_columns": evidence_columns or list(merged_keys.keys()),
            }

        normalized_rows = [_normalize_finding_row(row) for row in rows if isinstance(row, dict)]
        sample_row = normalized_rows[0] if normalized_rows else {}
        status = str(raw.get("status", "")).strip() or None
        error_summary = str(raw.get("error_summary", "")).strip() or None
        summary = f"{int(raw.get('finding_count', 0) or 0)} hallazgos detectados"
        if status == "SKIPPED" and error_summary:
            summary = error_summary

        return UISectionItem(
            id=test_id or None,
            title=test_id or None,
            subtitle=str(raw.get("fraud_type", "")).strip() or catalog_meta.get("fraud_type"),
            status=status,
            summary=summary,
            attributes={
                "finding_count": int(raw.get("finding_count", 0) or 0),
                "columns": evidence_columns,
                "evidence_columns": evidence_columns,
                "sample_entity_key": sample_row.get("entity_key") or first_row.get("entity_key"),
                "sample_keys": sample_row.get("keys", {}),
                "sample_query_id": sample_row.get("query_id"),
                "sample_drilldown_template": sample_row.get("drilldown_template", {}),
                "required_keys": sample_row.get("required_keys", []),
                "missing_keys": sample_row.get("missing_keys", []),
                "drilldown_ready": sample_row.get("drilldown_ready", False),
                "drilldown_error": sample_row.get("drilldown_error"),
                "error_summary": error_summary,
                "process_step": metadata.get("process_step") or catalog_meta.get("process_step"),
                "catalog_name": catalog_meta.get("name"),
                "catalog_description": catalog_meta.get("description"),
                "applicability_status": metadata.get("applicability_status"),
                "applicability_reason": metadata.get("applicability_reason"),
                "rows": normalized_rows,
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
        test_id = str(raw.get("test_id", "")).strip()
        catalog_meta = _catalog_metadata_for_test_id(test_id)
        status = str(raw.get("status", "")).strip().upper()
        summary = str(raw.get("summary", "")).strip()
        is_technical_error = status in {"ERROR", "TIMEOUT"} or "error_summary" in summary.lower() or "logs del runner" in summary.lower()
        return UISectionItem(
            id=test_id or None,
            title=test_id or None,
            subtitle=str(raw.get("fraud_type", "")).strip() or catalog_meta.get("fraud_type"),
            status=status or None,
            summary=summary or None,
            attributes={
                "cited_test_id": raw.get("cited_test_id"),
                "cited_keys": raw.get("cited_keys", {}),
                "referenced_columns": list(raw.get("referenced_columns", [])),
                "process_step": raw.get("process_step") or catalog_meta.get("process_step"),
                "finding_count": raw.get("finding_count"),
                "sample_entity_key": raw.get("sample_entity_key"),
                "catalog_name": catalog_meta.get("name"),
                "catalog_description": catalog_meta.get("description"),
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
    related_comparison_payload = _build_related_comparison_payload(
        run_id=run_id,
        scope=scope,
        settings=settings,
        s3_client=client,
    )
    if isinstance(second_level, dict):
        llm_insights = second_level.get("llm_insights", {}) if isinstance(second_level.get("llm_insights"), dict) else {}
        deterministic = second_level.get("deterministic_comparison", {}) if isinstance(second_level.get("deterministic_comparison"), dict) else {}
        normalized = llm_insights.get("normalized", {}) if isinstance(llm_insights.get("normalized"), dict) else {}
        executive_summary = _normalize_executive_summary(
            normalized.get("executive_summary") or llm_insights.get("executive_summary")
        )

        for idx, item in enumerate(normalized.get("recommendation_items", []), start=1):
            if not isinstance(item, dict):
                continue
            ui_item = _ui_item_from_normalized_item(raw=item, prefix="second-level", idx=idx)
            if ui_item is not None:
                second_level_items.append(ui_item)

        comparison_source_items = normalized.get("comparison_items") if isinstance(normalized.get("comparison_items"), list) else []
        deterministic_items = deterministic.get("comparison_sections", []) if isinstance(deterministic, dict) else []
        related_items = related_comparison_payload.get("comparison_sections", []) if isinstance(related_comparison_payload, dict) else []
        comparison_source_items = _merge_comparison_source_items(
            llm_items=[item for item in comparison_source_items if isinstance(item, dict)],
            deterministic_items=[item for item in deterministic_items if isinstance(item, dict)],
            related_items=[item for item in related_items if isinstance(item, dict)],
        )

        for idx, item in enumerate(comparison_source_items, start=1):
            if not isinstance(item, dict):
                continue
            ui_item = _ui_item_from_normalized_item(raw=item, prefix="comparison", idx=idx)
            if ui_item is not None:
                comparison_items.append(ui_item)

    if _looks_like_deterministic_summary(executive_summary or ""):
        executive_summary = _synthesize_executive_summary(
            explanations=[item for item in explanations if isinstance(item, dict)],
            findings=[item for item in findings if isinstance(item, dict)],
            scores=[item for item in scores if isinstance(item, dict)],
        )

    if executive_summary is None:
        executive_summary = _synthesize_executive_summary(
            explanations=[item for item in explanations if isinstance(item, dict)],
            findings=[item for item in findings if isinstance(item, dict)],
            scores=[item for item in scores if isinstance(item, dict)],
        )

    ui_hypotheses = [_as_ui_item(raw=item, kind="hypothesis") for item in hypotheses if isinstance(item, dict)]
    ui_selected_tests = [_as_ui_item(raw=item, kind="selected_test") for item in selected_tests if isinstance(item, dict)]
    ui_findings = [_as_ui_item(raw=item, kind="finding") for item in findings if isinstance(item, dict)]
    findings_by_test_id = {str(item.id or "").strip(): item for item in ui_findings if str(item.id or "").strip()}
    selected_by_test_id = {str(item.id or "").strip(): item for item in ui_selected_tests if str(item.id or "").strip()}
    ui_explanations = [_as_ui_item(raw=item, kind="explanation") for item in explanations if isinstance(item, dict)]
    for item in ui_explanations:
        test_id = str(item.id or "").strip()
        if not test_id:
            continue
        related_finding = findings_by_test_id.get(test_id)
        if related_finding is None:
            continue
        if item.attributes.get("finding_count") in (None, ""):
            item.attributes["finding_count"] = related_finding.attributes.get("finding_count")
        if not item.attributes.get("process_step"):
            item.attributes["process_step"] = related_finding.attributes.get("process_step")
        if not item.subtitle:
            item.subtitle = related_finding.subtitle

    explanations_by_test_id = {str(item.id or "").strip(): item for item in ui_explanations if str(item.id or "").strip()}
    for item in second_level_items:
        section = str(item.attributes.get("section") or "").strip()
        if section != "recommended_tests":
            continue
        test_id = str(item.attributes.get("test_id") or "").strip()
        if not test_id:
            if str(item.title or "").strip().startswith("TST-"):
                test_id = str(item.title or "").strip()
            elif str(item.summary or "").strip().startswith("TST-"):
                test_id = str(item.summary or "").strip()
        if not test_id:
            continue
        selected_test = selected_by_test_id.get(test_id)
        explanation = explanations_by_test_id.get(test_id)
        related_finding = findings_by_test_id.get(test_id)
        catalog_meta = _catalog_metadata_for_test_id(test_id)
        item.title = test_id
        if not str(item.summary or "").strip() or str(item.summary or "").strip() == test_id:
            item.summary = (
                (selected_test.summary if selected_test and selected_test.summary else None)
                or (explanation.summary if explanation and explanation.summary else None)
                or catalog_meta.get("description")
                or "Test sugerido para ampliar el contraste del caso."
            )
        item.subtitle = (
            item.subtitle
            or (selected_test.attributes.get("hypothesis_id") if selected_test else None)
            or (related_finding.subtitle if related_finding else None)
            or catalog_meta.get("fraud_type")
        )
        item.attributes["test_id"] = test_id
        if selected_test:
            if selected_test.status:
                item.attributes.setdefault("source", selected_test.status)
            process_step = selected_test.attributes.get("process_step")
            if process_step:
                item.attributes.setdefault("process_step", process_step)
            hypothesis_id = selected_test.attributes.get("hypothesis_id")
            if hypothesis_id:
                item.attributes.setdefault("hypothesis_id", hypothesis_id)
        if related_finding and related_finding.attributes.get("process_step"):
            item.attributes.setdefault("process_step", related_finding.attributes.get("process_step"))

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
        hypotheses=ui_hypotheses,
        selected_tests=ui_selected_tests,
        findings=ui_findings,
        scores=[_as_ui_item(raw=item, kind="score") for item in scores if isinstance(item, dict)],
        explanations=ui_explanations,
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
