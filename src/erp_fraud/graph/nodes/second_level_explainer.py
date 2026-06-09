"""Nodo/agente RF16 de segundo nivel (comparación inter-runs + recomendaciones)."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import yaml

from ...config import DEFAULT_BASE_DIR, DEFAULT_KB_CHROMA_CONFIG
from ...storage.runs_comparison import (
    build_comparison_markdown,
    compare_runs,
    pick_latest_run_ids_by_process_family,
)
from ..llm_runtime import call_openai_json, resolve_node_runtime_target
from ..state import GraphState
from .alpha_runtime import load_node_prompt, record_graph_node_model_config, run_alpha_loop_for_node
from .common import annotate_node_llm_mode, resolve_project_path
from . import deps
from .persist_utils import write_json

_run_alpha_loop_for_node = run_alpha_loop_for_node


SECOND_LEVEL_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "required": [],
    "properties": {
        "executive_summary": {
            "type": "object",
            "additionalProperties": True,
            "required": [],
            "properties": {
                "overall_assessment": {"type": "string"},
                "risk_posture": {"type": "string"},
                "key_observations": {"type": "array", "items": {"type": "string"}},
            },
        },
        "cross_process_conclusions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": [],
                "properties": {
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "summary": {"type": "string"},
                    "implication": {"type": "string"},
                    "recommendation": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "section": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
        "audit_procedures": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": [],
                "properties": {
                    "procedure": {"type": "string"},
                    "why": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "string"},
                },
            },
        },
        "recommended_tests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": [],
                "properties": {
                    "test_id": {"type": "string"},
                    "rationale": {"type": "string"},
                    "priority": {"type": "string"},
                    "expected_value": {"type": "string"},
                },
            },
        },
        "next_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": [],
                "properties": {
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                    "owner": {"type": "string"},
                    "urgency": {"type": "string"},
                },
            },
        },
    },
}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_structured_value(value: Any) -> Any:
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


def _short_text(value: Any, *, max_chars: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 14)].rstrip() + "...[truncated]"


def _artifact_payload_from_metadata(metadata: dict[str, Any], artifact_key: str) -> Any:
    artifacts = metadata.get("persist_artifacts", {})
    if not isinstance(artifacts, dict):
        return None
    path_value = str(artifacts.get(artifact_key, "")).strip()
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _state_list_or_artifact(*, state_values: Any, metadata: dict[str, Any], artifact_key: str) -> list[dict[str, Any]]:
    rows = [row for row in _safe_list(state_values) if isinstance(row, dict)]
    if rows:
        return rows
    loaded = _artifact_payload_from_metadata(metadata, artifact_key)
    return [row for row in _safe_list(loaded) if isinstance(row, dict)]


def _score_ranking_rows(scores: list[dict[str, Any]], ranking: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in ranking if isinstance(row, dict)]
    for score_payload in scores:
        score_rows = _safe_list(score_payload.get("ranking"))
        rows.extend(row for row in score_rows if isinstance(row, dict))
    dedup: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("entity_key", "")).strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        dedup.append(row)
    return sorted(dedup, key=lambda item: _as_float(item.get("score_total")), reverse=True)


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _best_metric_value(row: dict[str, Any]) -> float:
    metrics = _safe_dict(row.get("metrics"))
    candidates = [
        metrics.get("z_score"),
        row.get("z_score"),
        metrics.get("threshold_gap"),
        row.get("threshold_gap"),
        metrics.get("duplicate_count"),
        row.get("duplicate_count"),
    ]
    return max((_as_float(value) for value in candidates), default=0.0)


def _evidence_for_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    evidence_columns = [str(col).strip() for col in _safe_list(row.get("evidence_columns")) if str(col).strip()]
    metrics = _safe_dict(row.get("metrics"))
    for col in evidence_columns:
        if col not in row and col not in metrics:
            continue
        observed = row.get(col, metrics.get(col))
        expected = ""
        if col in {"betrag", "amount", "invoice_amount", "net_value"}:
            expected = row.get("mean_betrag") or row.get("expected_amount") or row.get("mean_amount") or ""
        if col in {"threshold", "threshold_gap"}:
            expected = row.get("threshold") or metrics.get("threshold") or ""
        evidence.append(
            {
                "evidence_type": col,
                "observed_value": _short_text(observed, max_chars=120),
                "expected_value": _short_text(expected, max_chars=120),
                "metric": _short_text(metrics.get(col, row.get("z_score", "")), max_chars=120),
            }
        )
        if len(evidence) >= 3:
            break
    return evidence


def _flatten_findings(*, findings: list[dict[str, Any]], score_by_entity: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for finding in findings:
        test_id = str(finding.get("test_id", "")).strip()
        fraud_type = str(finding.get("fraud_type", "")).strip()
        finding_count = int(finding.get("finding_count", 0) or 0)
        rows = [row for row in _safe_list(finding.get("rows")) if isinstance(row, dict)]
        if not rows and finding_count > 0:
            rows = [{}]
        for row in rows:
            entity_key = str(row.get("entity_key", "")).strip() or test_id
            score_row = score_by_entity.get(entity_key, {})
            score = _as_float(score_row.get("score_total")) or _best_metric_value(row)
            flattened.append(
                {
                    "test_id": test_id,
                    "fraud_type": fraud_type,
                    "entity_id": entity_key,
                    "score": score,
                    "finding_count": finding_count,
                    "anomaly_description": _describe_finding_row(test_id=test_id, fraud_type=fraud_type, row=row),
                    "evidence": _evidence_for_row(row),
                }
            )
    return sorted(flattened, key=lambda item: _as_float(item.get("score")), reverse=True)


def _describe_finding_row(*, test_id: str, fraud_type: str, row: dict[str, Any]) -> str:
    keys = _safe_dict(row.get("keys"))
    metrics = _safe_dict(row.get("metrics"))
    parts = [f"test_id={test_id}", f"fraud_type={fraud_type}"]
    for key, value in list(keys.items())[:4]:
        parts.append(f"{key}={value}")
    for key in ("betrag", "amount", "threshold", "threshold_gap", "z_score", "line_count", "total_betrag"):
        if key in row:
            parts.append(f"{key}={row.get(key)}")
    for key, value in list(metrics.items())[:3]:
        parts.append(f"{key}={value}")
    return _short_text("; ".join(str(part) for part in parts if str(part).strip()), max_chars=360)


def _compact_explanations(explanations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in explanations[:10]:
        summary = _short_text(row.get("summary"), max_chars=360)
        if not summary:
            continue
        out.append(
            {
                "test_id": str(row.get("test_id") or row.get("cited_test_id") or "").strip(),
                "fraud_type": str(row.get("fraud_type") or "").strip(),
                "entity_id": str(row.get("sample_entity_key") or "").strip(),
                "summary": summary,
            }
        )
    return out


def _load_catalog_tests(*, metadata: dict[str, Any], executed_test_ids: set[str]) -> list[dict[str, Any]]:
    catalog_path = resolve_project_path(str(metadata.get("catalog_path", "tests/catalog")).strip() or "tests/catalog")
    root = Path(catalog_path)
    if not root.exists():
        return []
    tests: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.y*ml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        test_id = str(payload.get("id") or payload.get("test_id") or "").strip()
        if not test_id or test_id in executed_test_ids:
            continue
        tests.append(
            {
                "test_id": test_id,
                "name": str(payload.get("name") or payload.get("title") or "").strip(),
                "fraud_type": str(payload.get("fraud_type") or "").strip(),
                "title": str(payload.get("title") or payload.get("name") or "").strip(),
                "why_applicable": str(payload.get("description") or payload.get("objective") or "").strip(),
            }
        )
    return tests[:20]


def _build_enriched_context(*, state: GraphState) -> dict[str, Any]:
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    findings = _state_list_or_artifact(state_values=state.findings, metadata=metadata, artifact_key="findings_json")
    scores = _state_list_or_artifact(state_values=state.scores, metadata=metadata, artifact_key="scores_json")
    explanations = _state_list_or_artifact(
        state_values=state.explanations,
        metadata=metadata,
        artifact_key="explanations_json",
    )
    selected_tests = _state_list_or_artifact(
        state_values=state.selected_tests,
        metadata=metadata,
        artifact_key="selected_tests_json",
    )
    ranking = [row for row in _safe_list(state.ranking) if isinstance(row, dict)]
    ranking_rows = _score_ranking_rows(scores, ranking)
    score_by_entity = {str(row.get("entity_key", "")).strip(): row for row in ranking_rows if str(row.get("entity_key", "")).strip()}
    top_findings = _flatten_findings(findings=findings, score_by_entity=score_by_entity)[:10]
    top_entities = [
        {
            "entity_id": str(row.get("entity_key", "")).strip(),
            "score_total": _as_float(row.get("score_total")),
            "fraud_types": [str(item).strip() for item in _safe_list(row.get("fraud_types")) if str(item).strip()],
            "tests_triggered": [str(item).strip() for item in _safe_list(row.get("tests_triggered")) if str(item).strip()],
        }
        for row in ranking_rows[:10]
    ]
    executed_test_ids = {
        str(row.get("test_id") or row.get("id") or "").strip()
        for row in selected_tests
        if str(row.get("test_id") or row.get("id") or "").strip()
    }
    context = {
        "availability": {
            "findings": len(findings),
            "scores": len(scores),
            "explanations": len(explanations),
            "selected_tests": len(selected_tests),
            "ranking_entities": len(ranking_rows),
        },
        "top_findings": top_findings,
        "top_entities": top_entities,
        "compact_explanations": _compact_explanations(explanations),
        "tests": {
            "executed_test_ids": sorted(executed_test_ids),
            "available_not_executed": _load_catalog_tests(metadata=metadata, executed_test_ids=executed_test_ids),
        },
    }
    return _truncate_enriched_context(context, max_chars=int(metadata.get("second_level_context_max_chars", 30000) or 30000))


def _truncate_enriched_context(context: dict[str, Any], *, max_chars: int) -> dict[str, Any]:
    if max_chars <= 0:
        return context
    out = json.loads(json.dumps(context, ensure_ascii=False, default=str))
    while len(json.dumps(out, ensure_ascii=False, default=str)) > max_chars:
        if len(_safe_list(out.get("compact_explanations"))) > 3:
            out["compact_explanations"] = out["compact_explanations"][: max(3, len(out["compact_explanations"]) // 2)]
            continue
        top_findings = _safe_list(out.get("top_findings"))
        reduced = False
        for row in top_findings:
            if isinstance(row, dict) and len(_safe_list(row.get("evidence"))) > 1:
                row["evidence"] = row["evidence"][:1]
                reduced = True
        if reduced:
            continue
        if len(top_findings) > 5:
            out["top_findings"] = top_findings[:5]
            continue
        if len(_safe_list(_safe_dict(out.get("tests")).get("available_not_executed"))) > 10:
            out["tests"]["available_not_executed"] = out["tests"]["available_not_executed"][:10]
            continue
        break
    return out


def _synthesize_audit_procedures(enriched_context: dict[str, Any]) -> list[dict[str, Any]]:
    procedures: list[dict[str, Any]] = []
    for row in _safe_list(enriched_context.get("top_findings"))[:6]:
        item = _safe_dict(row)
        test_id = str(item.get("test_id", "")).strip()
        entity_id = str(item.get("entity_id", "")).strip()
        if not test_id and not entity_id:
            continue
        evidence = [
            f"{_safe_dict(ev).get('evidence_type')}: {_safe_dict(ev).get('observed_value')}"
            for ev in _safe_list(item.get("evidence"))[:3]
            if isinstance(ev, dict)
        ]
        procedures.append(
            {
                "procedure": f"Revisar manualmente la entidad {entity_id or 'sin_clave'} disparada por {test_id or 'test_desconocido'}.",
                "why": _short_text(item.get("anomaly_description"), max_chars=260)
                or "El hallazgo aparece entre las señales priorizadas del run.",
                "evidence": evidence or [entity_id or test_id],
                "priority": "high" if _as_float(item.get("score")) >= 10 else "medium",
            }
        )
    return procedures


def _risk_posture_from_payload(*, deterministic_payload: dict[str, Any]) -> str:
    runs = _safe_list(deterministic_payload.get("runs"))
    current = _safe_dict(runs[0]) if runs else {}
    try:
        confidence = float(current.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence >= 0.75:
        return "Alto"
    if confidence >= 0.45:
        return "Medio"
    return "Moderado"


def _normalize_executive_summary(*, raw: Any, deterministic_payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_structured_value(raw)
    if isinstance(parsed, dict):
        overall = str(
            parsed.get("overall_assessment")
            or parsed.get("summary")
            or parsed.get("executive_summary")
            or ""
        ).strip()
        risk_posture = str(parsed.get("risk_posture") or "").strip() or _risk_posture_from_payload(
            deterministic_payload=deterministic_payload
        )
        observations = parsed.get("key_observations")
        if not isinstance(observations, list):
            observations = parsed.get("key_evidence")
        key_observations = [str(item).strip() for item in _safe_list(observations) if str(item).strip()]
        if not overall:
            overall = (
                "El second-level explainer consolida la lectura del run a partir de la señal actual, "
                "la comparación disponible y el contexto documental recuperado."
            )
        return {
            "overall_assessment": overall,
            "risk_posture": risk_posture,
            "key_observations": key_observations[:6],
        }

    text = str(parsed or "").strip()
    if not text:
        text = (
            "El second-level explainer no recibió suficiente contexto narrativo y se usa una síntesis determinista "
            "basada en el run actual y las comparativas disponibles."
        )
    return {
        "overall_assessment": text,
        "risk_posture": _risk_posture_from_payload(deterministic_payload=deterministic_payload),
        "key_observations": [],
    }


def _normalize_action_items(*, raw_items: Any, kind: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(_safe_list(raw_items), start=1):
        parsed = _parse_structured_value(raw)
        if isinstance(parsed, dict):
            if kind == "recommended_tests":
                normalized.append(
                    {
                        "title": str(parsed.get("test_id") or parsed.get("title") or f"Test recomendado {idx}").strip(),
                        "summary": str(parsed.get("rationale") or parsed.get("reason") or parsed.get("summary") or "").strip(),
                        "status": "recommended_test",
                        "section": "recommended_tests",
                        "priority": str(parsed.get("priority") or "").strip() or None,
                        "expected_value": str(parsed.get("expected_value") or "").strip() or None,
                        "attributes": parsed,
                    }
                )
            elif kind == "audit_procedures":
                normalized.append(
                    {
                        "title": str(parsed.get("procedure") or parsed.get("title") or f"Procedimiento {idx}").strip(),
                        "summary": str(parsed.get("why") or parsed.get("summary") or "").strip(),
                        "status": "audit_procedure",
                        "section": "audit_procedures",
                        "priority": str(parsed.get("priority") or "").strip() or None,
                        "evidence": _safe_list(parsed.get("evidence")),
                        "attributes": parsed,
                    }
                )
            else:
                normalized.append(
                    {
                        "title": str(parsed.get("action") or parsed.get("title") or f"Recomendación {idx}").strip(),
                        "summary": str(parsed.get("why") or parsed.get("summary") or "").strip(),
                        "status": "recommended_action",
                        "section": "recommendations",
                        "owner": str(parsed.get("owner") or "").strip() or None,
                        "urgency": str(parsed.get("urgency") or "").strip() or None,
                        "attributes": parsed,
                    }
                )
            continue

        text = str(parsed or "").strip()
        if not text:
            continue
        base = {
            "title": (
                f"Test recomendado {idx}" if kind == "recommended_tests"
                else f"Procedimiento {idx}" if kind == "audit_procedures"
                else f"Recomendación {idx}"
            ),
            "summary": text,
            "attributes": {},
        }
        if kind == "recommended_tests":
            base.update({"status": "recommended_test", "section": "recommended_tests"})
        elif kind == "audit_procedures":
            base.update({"status": "audit_procedure", "section": "audit_procedures"})
        else:
            base.update({"status": "recommended_action", "section": "recommendations"})
        normalized.append(base)
    return normalized


def _recommended_test_identity(item: Any) -> str:
    parsed = _parse_structured_value(item)
    if isinstance(parsed, dict):
        for key in ("test_id", "id", "name", "title"):
            value = str(parsed.get(key) or "").strip()
            if value:
                return value
        return ""
    return str(parsed or "").strip()


def _filter_recommended_tests_against_executed(
    *,
    recommended_tests: Any,
    executed_test_ids: Any,
    available_tests_not_executed: Any,
) -> tuple[list[Any], list[str]]:
    executed = {str(item).strip() for item in _safe_list(executed_test_ids) if str(item).strip()}
    allowed = {
        str(_safe_dict(item).get("test_id") or "").strip()
        for item in _safe_list(available_tests_not_executed)
        if str(_safe_dict(item).get("test_id") or "").strip()
    }
    raw_items = _safe_list(recommended_tests)
    if not raw_items:
        return [], []

    filtered: list[Any] = []
    removed: list[str] = []
    removed_seen: set[str] = set()
    for item in raw_items:
        test_id = _recommended_test_identity(item)
        should_remove = bool(test_id and test_id in executed) or not bool(test_id and test_id in allowed)
        if should_remove:
            if test_id and test_id not in removed_seen:
                removed.append(test_id)
                removed_seen.add(test_id)
            continue
        filtered.append(item)
    return filtered, removed


def _fallback_recommended_tests_from_candidates(*, available_tests_not_executed: Any, max_items: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _safe_list(available_tests_not_executed):
        item = _safe_dict(row)
        test_id = str(item.get("test_id") or "").strip()
        if not test_id or test_id in seen:
            continue
        seen.add(test_id)
        fraud_type = str(item.get("fraud_type") or "").strip()
        title = str(item.get("title") or item.get("name") or "").strip()
        reason_tail = f" sobre {fraud_type}" if fraud_type else ""
        if title:
            reason_tail += f" ({title})"
        reason = (
            "No se ejecutó en el run actual y es compatible como prueba complementaria "
            f"para ampliar cobertura{reason_tail}."
        )
        out.append(
            {
                "test_id": test_id,
                "reason": reason,
                "rationale": reason,
                "priority": "medium",
                "expected_value": "Ampliar cobertura con una prueba del catálogo no ejecutada en este run.",
                "source": "deterministic_available_not_executed_fallback",
            }
        )
        if len(out) >= max_items:
            break
    return out


def _normalize_comparison_items(*, raw_items: Any, deterministic_payload: dict[str, Any]) -> list[dict[str, Any]]:
    current_runs = _safe_list(deterministic_payload.get("runs"))
    default_runs = [str(_safe_dict(row).get("run_id", "")).strip() for row in current_runs if str(_safe_dict(row).get("run_id", "")).strip()]
    items: list[dict[str, Any]] = []
    for idx, raw in enumerate(_safe_list(raw_items), start=1):
        parsed = _parse_structured_value(raw)
        if isinstance(parsed, dict):
            title = str(parsed.get("title") or parsed.get("conclusion") or f"Comparativa {idx}").strip()
            summary = str(parsed.get("summary") or parsed.get("implication") or parsed.get("conclusion") or "").strip()
            items.append(
                {
                    "title": title,
                    "subtitle": str(parsed.get("subtitle") or "Comparativa contextual del caso").strip(),
                    "summary": summary,
                    "status": str(parsed.get("status") or "comparison").strip(),
                    "section": str(parsed.get("section") or "cross_process").strip(),
                    "implication": str(parsed.get("implication") or "").strip() or None,
                    "recommendation": str(parsed.get("recommendation") or "").strip() or None,
                    "evidence": [str(item).strip() for item in _safe_list(parsed.get("evidence")) if str(item).strip()],
                    "attributes": {
                        **parsed,
                        "runs_compared": _safe_list(parsed.get("runs_compared")) or default_runs,
                    },
                }
            )
            continue
        text = str(parsed or "").strip()
        if text:
            items.append(
                {
                    "title": f"Comparativa {idx}",
                    "subtitle": "Comparativa contextual del caso",
                    "summary": text,
                    "status": "comparison",
                    "section": "cross_process",
                    "attributes": {"runs_compared": default_runs},
                }
            )
    return items


def _resolve_rf16_run_ids(*, state: GraphState) -> list[str]:
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    run_id = str(state.run_id).strip()
    configured = metadata.get("rf16_compare_run_ids", [])
    run_ids: list[str] = []
    if isinstance(configured, str):
        run_ids = [item.strip() for item in configured.split(",") if item.strip()]
    elif isinstance(configured, list):
        run_ids = [str(item).strip() for item in configured if str(item).strip()]

    auto_latest = bool(metadata.get("rf16_auto_latest_p2p_o2c", True))
    base_dir = str(metadata.get("rf16_base_dir", metadata.get("persist_base_dir", "run_results"))).strip() or "run_results"
    if not run_ids and auto_latest:
        run_ids = pick_latest_run_ids_by_process_family(base_dir=base_dir)

    include_current = bool(metadata.get("rf16_include_current_run", True))
    if include_current and run_id:
        run_ids = [run_id, *run_ids]

    dedup: list[str] = []
    seen: set[str] = set()
    for item in run_ids:
        rid = str(item).strip()
        if not rid or rid in seen:
            continue
        dedup.append(rid)
        seen.add(rid)
    return dedup


def _insufficient_context_comparison_payload(
    *,
    run_id: str,
    base_dir: str,
    metadata: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    process_family = str(metadata.get("process_family", "")).strip()
    return {
        "rf_task": "RF16",
        "generated_at_utc": "",
        "runs_count": 1 if run_id else 0,
        "process_families": {process_family: 1} if process_family else {},
        "comparison_status": "INSUFFICIENT_CONTEXT",
        "degraded_reason": reason,
        "runs": [
            {
                "run_id": run_id,
                "dataset_id": str(metadata.get("dataset_id", "")).strip(),
                "dataset_hash": str(metadata.get("dataset_hash", "")).strip(),
                "process_family": process_family,
                "llm_mode": str(metadata.get("llm_mode", "")).strip(),
                "graph_status": str(metadata.get("graph_status", "")).strip(),
                "overall_status": str(metadata.get("overall_status", "")).strip(),
                "hypotheses_count": 0,
                "selected_tests_count": 0,
                "selected_test_ids": [],
                "findings_total": 0,
                "tests_with_findings": [],
                "fraud_types_with_findings": {},
                "final_label": "",
                "confidence": 0.0,
                "langsmith_trace_link": "",
                "generated_at_utc": "",
            }
        ]
        if run_id
        else [],
        "summary": {
            "current_run_id": run_id,
            "historical_run_ids": [],
            "cross_process_run_ids": [],
            "common_selected_tests": [],
            "common_fraud_types_with_findings": [],
            "pairwise_similarity": [],
        },
        "comparison_sections": [
            {
                "title": "Contexto insuficiente para comparación de segundo nivel",
                "subtitle": "Second-level explainer degradado",
                "summary": (
                    "No se dispone de artefactos comparables suficientes en el workspace local del run cloud; "
                    "se genera una salida parcial para no invalidar el análisis principal."
                ),
                "status": "insufficient_context",
                "section": "current_run",
                "evidence": [reason],
            }
        ],
        "recommendations": [
            {
                "id": "REC-INSUFFICIENT-CONTEXT",
                "severity": "low",
                "title": "Completar contexto comparable antes de interpretar convergencias",
                "run_id": run_id,
                "rationale": "La comparación RF16 no pudo usar histórico o familia cruzada en el filesystem local.",
                "actions": [
                    "Revisar los artefactos del run actual desde el reporte principal.",
                    "Ejecutar o sincronizar runs comparables antes de usar conclusiones cross-run.",
                ],
            }
        ],
    }


def _compare_runs_degrading_on_missing_context(
    *,
    run_ids: list[str],
    base_dir: str,
    state: GraphState,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    try:
        return compare_runs(run_ids=run_ids, base_dir=base_dir)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        metadata["second_level_comparison_status"] = "INSUFFICIENT_CONTEXT"
        metadata["second_level_comparison_error"] = reason
        root = Path(base_dir)
        existing_run_ids = [rid for rid in run_ids if rid and (root / rid).is_dir()]
        if existing_run_ids and existing_run_ids != run_ids:
            try:
                payload = compare_runs(run_ids=existing_run_ids, base_dir=base_dir)
                payload["comparison_status"] = "INSUFFICIENT_CONTEXT"
                payload["degraded_reason"] = reason
                metadata["second_level_explainer_degraded"] = True
                metadata["second_level_explainer_degraded_reason"] = reason
                metadata["second_level_explainer_available_run_ids"] = existing_run_ids
                return payload
            except Exception as fallback_exc:
                reason = f"{reason}; fallback={type(fallback_exc).__name__}: {fallback_exc}"
                metadata["second_level_comparison_error"] = reason
        metadata["second_level_explainer_degraded"] = True
        metadata["second_level_explainer_degraded_reason"] = reason
        return _insufficient_context_comparison_payload(
            run_id=str(state.run_id).strip(),
            base_dir=base_dir,
            metadata=metadata,
            reason=reason,
        )


def _validate_second_level_output(output: Any, _input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {"passed": False, "errors": ["second_level output debe ser objeto"]}
    required_lists = ("audit_procedures", "recommended_tests", "next_actions")
    for field in required_lists:
        if field in output and not isinstance(output.get(field), list):
            return {"passed": False, "errors": [f"campo requerido debe ser lista: {field}"]}
    if not (
        _safe_list(output.get("audit_procedures"))
        or _safe_list(output.get("recommended_tests"))
        or _safe_list(output.get("next_actions"))
    ):
        return {"passed": False, "errors": ["el agente debe proponer al menos una acción/procedimiento/test"]}
    return {"passed": True, "errors": []}


def _looks_like_executive_summary_fragment(output: Any) -> bool:
    if not isinstance(output, dict):
        return False
    root_keys = {"executive_summary", "cross_process_conclusions", "audit_procedures", "recommended_tests", "next_actions"}
    if any(key in output for key in root_keys):
        return False
    summary_keys = {"overall_assessment", "risk_posture", "key_observations", "summary", "key_evidence"}
    return any(key in output for key in summary_keys)


def _coerce_second_level_root_output(
    output: Any,
    *,
    fallback_insights: dict[str, Any],
    metadata: dict[str, Any],
) -> Any:
    if not _looks_like_executive_summary_fragment(output):
        return output

    fallback_root = dict(fallback_insights)
    fallback_root["executive_summary"] = output
    metadata["second_level_executive_summary_fragment_wrapped"] = True
    return fallback_root


def _alpha_loop_diagnostics(metadata: dict[str, Any], *, node_id: str) -> dict[str, Any]:
    alpha_meta = metadata.get("alphacodium", {})
    node_meta = _safe_dict(_safe_dict(alpha_meta).get(node_id))
    last_validation = _safe_dict(node_meta.get("last_validation"))
    checks = _safe_list(last_validation.get("checks"))
    validation_errors: list[str] = []
    for check in checks:
        item = _safe_dict(check)
        for err in _safe_list(item.get("errors")):
            text = str(err).strip()
            if text:
                validation_errors.append(text)
    iterations = int(node_meta.get("iterations", 0) or 0)
    return {
        "alpha_loop_final_state": str(node_meta.get("status") or "unknown").strip() or "unknown",
        "alpha_loop_error_detail": "; ".join(validation_errors) or "unknown",
        "alpha_loop_iterations": iterations,
        "alpha_loop_retries_done": max(0, iterations - 1),
        "validation_error": validation_errors[0] if validation_errors else "unknown",
    }


def _log_second_level_llm_output(
    *,
    output: Any,
    metadata: dict[str, Any],
    iteration: int,
    repair_feedback: list[str],
) -> None:
    max_chars = int(metadata.get("second_level_llm_output_log_max_chars", 6000) or 6000)
    text = json.dumps(output, ensure_ascii=False, sort_keys=True, default=str)
    truncated = max_chars > 0 and len(text) > max_chars
    payload = {
        "event": "second_level_llm_output_before_validation",
        "iteration": iteration,
        "repair_feedback": repair_feedback,
        "output": text[:max_chars] if truncated else text,
        "output_truncated": truncated,
        "output_length": len(text),
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def _fallback_llm_insights(*, deterministic_payload: dict[str, Any]) -> dict[str, Any]:
    recs = _safe_list(deterministic_payload.get("recommendations"))
    summary = _safe_dict(deterministic_payload.get("summary"))
    common_types = _safe_list(summary.get("common_fraud_types_with_findings"))
    actions: list[str] = []
    tests: list[str] = []
    procedures: list[str] = []
    for rec in recs:
        item = _safe_dict(rec)
        for row in _safe_list(item.get("actions")):
            action = str(row).strip()
            if action and action not in actions:
                actions.append(action)
    for run in _safe_list(deterministic_payload.get("runs")):
        item = _safe_dict(run)
        for test_id in _safe_list(item.get("selected_test_ids")):
            tid = str(test_id).strip()
            if tid and tid not in tests:
                tests.append(tid)
    for row in actions:
        if "auditor" in row.lower() or "reconcili" in row.lower() or "revisi" in row.lower():
            procedures.append(row)
    comparison_sections = _safe_list(deterministic_payload.get("comparison_sections"))
    current_section = _safe_dict(comparison_sections[0]) if comparison_sections else {}
    executive_summary = {
        "overall_assessment": str(current_section.get("summary") or "").strip()
        or "El second-level explainer usa una síntesis determinista basada en el run actual y la comparación disponible.",
        "risk_posture": _risk_posture_from_payload(deterministic_payload=deterministic_payload),
        "key_observations": [
            f"Tipologías comunes con hallazgos: {', '.join(common_types) if common_types else 'ninguna'}.",
            f"Runs comparados: {int(deterministic_payload.get('runs_count', 0) or 0)}.",
        ],
    }
    return {
        "executive_summary": executive_summary,
        "cross_process_conclusions": comparison_sections,
        "audit_procedures": procedures[:6],
        "recommended_tests": tests[:8],
        "next_actions": actions[:8],
    }


def _build_doc_first_query(*, deterministic_payload: dict[str, Any]) -> str:
    runs = _safe_list(deterministic_payload.get("runs"))
    process_families = sorted(
        {
            str(_safe_dict(row).get("process_family", "")).strip()
            for row in runs
            if str(_safe_dict(row).get("process_family", "")).strip()
        }
    )
    common_types = _safe_list(_safe_dict(deterministic_payload.get("summary")).get("common_fraud_types_with_findings"))
    labels = sorted(
        {
            str(_safe_dict(row).get("final_label", "")).strip()
            for row in runs
            if str(_safe_dict(row).get("final_label", "")).strip()
        }
    )
    return (
        "documentacion proyecto ERP fraude "
        "procedimientos auditoria recomendaciones "
        f"process_families={'/'.join(process_families) if process_families else 'unknown'} "
        f"fraud_types={' '.join(str(x).strip() for x in common_types if str(x).strip())} "
        f"labels={' '.join(labels)}"
    ).strip()


def _build_second_level_markdown(*, deterministic_payload: dict[str, Any], llm_insights: dict[str, Any]) -> str:
    base = build_comparison_markdown(deterministic_payload).rstrip()
    lines = [base, "", "## Conclusiones LLM (Agente 2º nivel)", ""]
    normalized = _safe_dict(llm_insights.get("normalized"))
    lines.append(f"- executive_summary: {json.dumps(normalized.get('executive_summary', {}), ensure_ascii=False)}")
    lines.append("- comparison_items:")
    for row in _safe_list(normalized.get("comparison_items"))[:8]:
        lines.append(f"  - {json.dumps(row, ensure_ascii=False)}")
    lines.append("- recommendation_items:")
    for row in _safe_list(normalized.get("recommendation_items"))[:12]:
        lines.append(f"  - {json.dumps(row, ensure_ascii=False)}")
    lines.append("")
    return "\n".join(lines)


def second_level_explainer_node(state: GraphState) -> GraphState:
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    llm_mode = annotate_node_llm_mode(metadata=metadata, node_id="second_level_explainer")
    runtime_target = resolve_node_runtime_target(
        node_id="second_level_explainer",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
    )
    record_graph_node_model_config(
        node_id="second_level_explainer",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
        overrides={
            "mode_effective": str(runtime_target.get("mode_effective", "stub_runtime")),
            "llm_mode": llm_mode,
            "real_mode_requested": llm_mode == "real",
            "provider": str(runtime_target.get("provider", "")).strip(),
            "model_used": str(runtime_target.get("model_used", "")).strip() or "gpt-5.4-mini",
        },
    )

    run_ids = _resolve_rf16_run_ids(state=state)
    base_dir = str(metadata.get("rf16_base_dir", metadata.get("persist_base_dir", "run_results"))).strip() or "run_results"
    deterministic_payload = _compare_runs_degrading_on_missing_context(
        run_ids=run_ids,
        base_dir=base_dir,
        state=state,
        metadata=metadata,
    )
    kb_enabled = bool(metadata.get("kb_search_enabled", False))
    kb_top_k = int(metadata.get("rf16_kb_top_k", 5) or 5)
    if kb_top_k <= 0:
        kb_top_k = 5
    kb_hits: list[dict[str, Any]] = []
    kb_status = "SKIPPED"
    kb_doc_hits: list[dict[str, Any]] = []
    kb_general_hits: list[dict[str, Any]] = []
    if kb_enabled:
        common_types = _safe_list(_safe_dict(deterministic_payload.get("summary")).get("common_fraud_types_with_findings"))
        query = str(metadata.get("rf16_kb_query", "")).strip()
        if not query:
            query = _build_doc_first_query(deterministic_payload=deterministic_payload)
        try:
            tool = deps.KBSearchTool(
                kb_chroma_config_path=resolve_project_path(
                    str(metadata.get("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)).strip()
                    or DEFAULT_KB_CHROMA_CONFIG
                ),
                base_dir=resolve_project_path(
                    str(metadata.get("base_dir", DEFAULT_BASE_DIR)).strip() or DEFAULT_BASE_DIR
                ),
            )
            doc_filters_candidates = [
                {"source_id": "project_docs_markdown"},
                {"source_id": "project_docs"},
                {"collection_type": "project_docs"},
            ]
            for filters in doc_filters_candidates:
                try:
                    kb_doc_out = tool.search(query=query, top_k=kb_top_k, filters=filters)
                except Exception:
                    kb_doc_out = {}
                hits = kb_doc_out.get("hits", []) if isinstance(kb_doc_out, dict) else []
                kb_doc_hits = [row for row in hits if isinstance(row, dict)]
                if kb_doc_hits:
                    break

            general_query = (
                "ACFE fraud red flags audit procedures "
                + " ".join(str(item).strip() for item in common_types if str(item).strip())
            ).strip()
            kb_out = tool.search(query=general_query, top_k=kb_top_k)
            hits = kb_out.get("hits", []) if isinstance(kb_out, dict) else []
            kb_general_hits = [row for row in hits if isinstance(row, dict)]
            kb_hits = [*kb_doc_hits]
            seen_chunks = {
                str(_safe_dict(item).get("chunk_id", "")).strip()
                for item in kb_hits
                if str(_safe_dict(item).get("chunk_id", "")).strip()
            }
            for hit in kb_general_hits:
                hid = str(_safe_dict(hit).get("chunk_id", "")).strip()
                if hid and hid in seen_chunks:
                    continue
                kb_hits.append(hit)
                if hid:
                    seen_chunks.add(hid)
                if len(kb_hits) >= kb_top_k:
                    break
            kb_status = "OK"
        except Exception as exc:
            kb_status = f"ERROR:{type(exc).__name__}"
    metadata["rf16_kb_search_status"] = kb_status
    metadata["rf16_kb_hits_count"] = len(kb_hits)
    metadata["rf16_kb_doc_hits_count"] = len(kb_doc_hits)
    metadata["rf16_kb_general_hits_count"] = len(kb_general_hits)

    fallback_insights = _fallback_llm_insights(deterministic_payload=deterministic_payload)
    prompt_info = load_node_prompt(
        node_id="second_level_explainer",
        fallback_text=(
            "Actúa como auditor senior. Analiza comparación de runs + KB documental y devuelve SOLO JSON con: "
            "executive_summary{overall_assessment,risk_posture,key_observations[]}, "
            "cross_process_conclusions[{title,subtitle,summary,implication,recommendation,evidence[],section,status}], "
            "audit_procedures[{procedure,why,evidence[],priority}], "
            "recommended_tests[{test_id,reason,rationale,priority,expected_value}], "
            "next_actions[{action,why,owner,urgency}]. "
            "Para audit_procedures, genera al menos un procedimiento auditor por cada hallazgo de top_findings; "
            "cada procedimiento debe referenciar el test_id y la entidad concreta. "
            "Para recommended_tests, recomienda únicamente tests presentes en available_tests_not_executed; "
            "no recomiendes tests ya ejecutados. Si no hay tests disponibles no ejecutados, devuelve recommended_tests: []. "
            "Cada recommended_test debe incluir test_id y reason. "
            "Para next_actions, prioriza acciones sobre entidades concretas, no acciones genéricas de configuración. "
            "Prioriza primero la documentación del proyecto y después ACFE/externo. "
            "No uses defaults; justifica acciones con evidencia de runs y KB cuando exista."
        ),
        registry_path=metadata.get("prompt_registry_path"),
    )
    prompt_text = str(prompt_info.get("text", "")).strip()
    metadata["second_level_prompt_path"] = str(prompt_info.get("path", "")).strip()
    metadata["second_level_prompt_version"] = str(prompt_info.get("version", "")).strip()
    metadata["second_level_prompt_hash"] = str(prompt_info.get("hash", "")).strip()
    metadata["second_level_prompt_status"] = str(prompt_info.get("status", "")).strip()

    runtime_by_node = metadata.setdefault("llm_runtime_by_node", {})
    if not isinstance(runtime_by_node, dict):
        runtime_by_node = {}
        metadata["llm_runtime_by_node"] = runtime_by_node

    def _generate(
        _prompt: str,
        input_payload: dict[str, Any],
        repair_feedback: list[str],
        _iteration: int,
    ) -> dict[str, Any]:
        output: dict[str, Any] | None = None
        if bool(runtime_target.get("enabled", False)):
            llm_output, llm_meta = call_openai_json(
                model_used=str(runtime_target.get("model_used", "")).strip() or "gpt-5.4-mini",
                temperature=float(runtime_target.get("temperature", 0.0) or 0.0),
                max_tokens=int(runtime_target.get("max_tokens", 0) or 0),
                prompt_text=prompt_text,
                input_payload=input_payload,
                repair_feedback=repair_feedback,
                timeout_s=float(metadata.get("llm_timeout_s", 30.0) or 30.0),
                max_retries=int(metadata.get("llm_max_retries", 1) or 1),
                retry_backoff_s=float(metadata.get("llm_retry_backoff_s", 0.6) or 0.6),
                json_schema=SECOND_LEVEL_OUTPUT_SCHEMA,
                json_schema_name="second_level_explainer_output",
                json_schema_strict=False,
                log_raw_response=True,
                raw_response_log_event="second_level_openai_raw_response",
                raw_response_max_chars=int(metadata.get("second_level_llm_output_log_max_chars", 6000) or 6000),
            )
            runtime_by_node["second_level_explainer"] = {
                "model_used": str(llm_meta.get("model_used", "")).strip()
                or str(runtime_target.get("model_used", "")).strip()
                or "gpt-5.4-mini",
                "llm_mode": llm_mode,
                "latency_ms": int(llm_meta.get("latency_ms", 0) or 0),
                "input_tokens": int(llm_meta.get("input_tokens", 0) or 0),
                "output_tokens": int(llm_meta.get("output_tokens", 0) or 0),
                "total_tokens": int(llm_meta.get("total_tokens", 0) or 0),
                "cost_estimated_usd": float(llm_meta.get("cost_estimated_usd", 0.0) or 0.0),
                "retries_done": int(llm_meta.get("retries_done", 0) or 0),
                "fallback_used": bool(llm_meta.get("fallback_used", llm_output is None)),
                "status": str(llm_meta.get("status", "UNKNOWN")).strip(),
            }
            if isinstance(llm_output, dict):
                output = _coerce_second_level_root_output(
                    llm_output,
                    fallback_insights=fallback_insights,
                    metadata=metadata,
                )
        else:
            model_config_by_node = metadata.get("agent_model_config", {})
            second_model_config = (
                _safe_dict(model_config_by_node.get("second_level_explainer"))
                if isinstance(model_config_by_node, dict)
                else {}
            )
            runtime_by_node["second_level_explainer"] = {
                "model_used": str(runtime_target.get("model_used", "")).strip() or "gpt-5.4-mini",
                "llm_mode": llm_mode,
                "latency_ms": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_estimated_usd": 0.0,
                "retries_done": 0,
                "fallback_used": True,
                "status": "SKIPPED",
                "skip_reason": str(runtime_target.get("reason") or "unknown").strip() or "unknown",
                "provider": str(runtime_target.get("provider") or "unknown").strip() or "unknown",
                "mode_effective": str(llm_mode or runtime_target.get("llm_mode") or "unknown").strip() or "unknown",
                "models_config_source": str(
                    second_model_config.get("source") or runtime_target.get("source") or "unknown"
                ).strip()
                or "unknown",
            }
        if not isinstance(output, dict):
            output = dict(fallback_insights)
        _log_second_level_llm_output(
            output=output,
            metadata=metadata,
            iteration=_iteration,
            repair_feedback=repair_feedback,
        )
        return output

    enriched_context = _build_enriched_context(state=state)
    metadata["second_level_context_availability"] = _safe_dict(enriched_context.get("availability"))
    metadata["second_level_context_top_findings_count"] = len(_safe_list(enriched_context.get("top_findings")))
    metadata["second_level_context_top_entities_count"] = len(_safe_list(enriched_context.get("top_entities")))
    metadata["second_level_context_explanations_count"] = len(_safe_list(enriched_context.get("compact_explanations")))
    metadata["second_level_context_available_tests_count"] = len(
        _safe_list(_safe_dict(enriched_context.get("tests")).get("available_not_executed"))
    )
    input_payload = {
        "deterministic_comparison": deterministic_payload,
        "kb_context": {
            "status": kb_status,
            "hits_count": len(kb_hits),
            "doc_hits_count": len(kb_doc_hits),
            "general_hits_count": len(kb_general_hits),
            "priority": "project_docs_first_then_external",
            "hits": kb_hits,
        },
        "run_context": {
            "run_id": str(state.run_id).strip(),
            "process_family": str(metadata.get("process_family", "")).strip(),
            "llm_mode": llm_mode,
        },
        "available_tests_not_executed": _safe_list(_safe_dict(enriched_context.get("tests")).get("available_not_executed"))[:15],
        "current_run_context": enriched_context,
    }
    try:
        llm_insights = _run_alpha_loop_for_node(
            state=state,
            node_id="second_level_explainer",
            prompt_text=prompt_text,
            input_payload=input_payload,
            generate_fn=_generate,
            validators={"second_level_schema": _validate_second_level_output},
            max_iter=2,
        )
    except RuntimeError as exc:
        reason = f"{type(exc).__name__}: {exc}"
        alpha_diag = _alpha_loop_diagnostics(metadata, node_id="second_level_explainer")
        alpha_loop_retries_done = int(alpha_diag.get("alpha_loop_retries_done", 0) or 0)
        existing_runtime = _safe_dict(runtime_by_node.get("second_level_explainer"))
        metadata["second_level_explainer_degraded"] = True
        metadata["second_level_explainer_degraded_reason"] = reason
        metadata["second_level_explainer_status"] = "OK_WITH_WARNINGS"
        runtime_by_node["second_level_explainer"] = {
            **existing_runtime,
            "fallback_used": True,
            "status": "DEGRADED",
            "degraded_reason": reason,
            "retries_done": max(int(existing_runtime.get("retries_done", 0) or 0), alpha_loop_retries_done),
            **alpha_diag,
        }
        llm_insights = dict(fallback_insights)
    alpha_diag = _alpha_loop_diagnostics(metadata, node_id="second_level_explainer")
    if alpha_diag.get("alpha_loop_final_state") != "unknown":
        existing_runtime = _safe_dict(runtime_by_node.get("second_level_explainer"))
        alpha_loop_retries_done = int(alpha_diag.get("alpha_loop_retries_done", 0) or 0)
        runtime_by_node["second_level_explainer"] = {
            **existing_runtime,
            "retries_done": max(int(existing_runtime.get("retries_done", 0) or 0), alpha_loop_retries_done),
            **alpha_diag,
        }
    if not isinstance(llm_insights, dict):
        llm_insights = dict(fallback_insights)
    if not _safe_list(llm_insights.get("audit_procedures")):
        synthetic_procedures = _synthesize_audit_procedures(enriched_context)
        if synthetic_procedures:
            llm_insights["audit_procedures"] = synthetic_procedures
            metadata["second_level_audit_procedures_synthesized"] = len(synthetic_procedures)

    tests_context = _safe_dict(enriched_context.get("tests"))
    executed_test_ids = _safe_list(tests_context.get("executed_test_ids"))
    available_tests_not_executed = _safe_list(tests_context.get("available_not_executed"))
    filtered_recommended_tests, filtered_out_test_ids = _filter_recommended_tests_against_executed(
        recommended_tests=llm_insights.get("recommended_tests", []),
        executed_test_ids=executed_test_ids,
        available_tests_not_executed=available_tests_not_executed,
    )
    fallback_used_for_recommended_tests = False
    if not filtered_recommended_tests and available_tests_not_executed:
        filtered_recommended_tests = _fallback_recommended_tests_from_candidates(
            available_tests_not_executed=available_tests_not_executed,
            max_items=3,
        )
        fallback_used_for_recommended_tests = bool(filtered_recommended_tests)
    llm_insights["recommended_tests"] = filtered_recommended_tests
    llm_insights["recommended_tests_candidate_count"] = len(available_tests_not_executed)
    llm_insights["recommended_tests_fallback_used"] = fallback_used_for_recommended_tests
    if filtered_out_test_ids:
        llm_insights["recommended_tests_filtered_out"] = filtered_out_test_ids
        metadata["second_level_recommended_tests_filtered_out_count"] = len(filtered_out_test_ids)
    metadata["second_level_recommended_tests_candidate_count"] = len(available_tests_not_executed)
    metadata["second_level_recommended_tests_fallback_used"] = fallback_used_for_recommended_tests

    normalized_insights = {
        "executive_summary": _normalize_executive_summary(
            raw=llm_insights.get("executive_summary"),
            deterministic_payload=deterministic_payload,
        ),
        "comparison_items": _normalize_comparison_items(
            raw_items=llm_insights.get("cross_process_conclusions", []),
            deterministic_payload=deterministic_payload,
        ) or _safe_list(deterministic_payload.get("comparison_sections")),
        "recommendation_items": [
            *_normalize_action_items(raw_items=llm_insights.get("next_actions", []), kind="next_actions"),
            *_normalize_action_items(raw_items=llm_insights.get("recommended_tests", []), kind="recommended_tests"),
            *_normalize_action_items(raw_items=llm_insights.get("audit_procedures", []), kind="audit_procedures"),
        ],
    }
    llm_insights = {
        **llm_insights,
        "normalized": normalized_insights,
    }

    final_payload = {
        "rf_task": "RF16",
        "analysis_scope": {
            "run_ids": run_ids,
            "base_dir": base_dir,
        },
        "deterministic_comparison": deterministic_payload,
        "llm_insights": llm_insights,
    }

    graph_dir = Path(str(metadata.get("persist_graph_dir", "")).strip() or Path(base_dir) / str(state.run_id).strip() / "graph")
    graph_dir.mkdir(parents=True, exist_ok=True)
    json_path = graph_dir / "second_level_analysis.json"
    md_path = graph_dir / "second_level_analysis.md"
    write_json(json_path, final_payload)
    md_path.write_text(
        _build_second_level_markdown(deterministic_payload=deterministic_payload, llm_insights=llm_insights),
        encoding="utf-8",
    )

    metadata["second_level_explainer_status"] = (
        "OK_WITH_WARNINGS" if bool(metadata.get("second_level_explainer_degraded", False)) else "OK"
    )
    metadata["second_level_explainer_runs_compared"] = run_ids
    metadata["second_level_analysis_json"] = str(json_path)
    metadata["second_level_analysis_md"] = str(md_path)
    artifacts = metadata.setdefault("persist_artifacts", {})
    if isinstance(artifacts, dict):
        artifacts["second_level_analysis_json"] = str(json_path)
        artifacts["second_level_analysis_md"] = str(md_path)
    state.export_paths["second_level_analysis_json"] = str(json_path)
    state.export_paths["second_level_analysis_md"] = str(md_path)

    state.recomendaciones = [
        {
            "source": "rf16_second_level",
            "action": str(item.get("title") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
        }
        for item in _safe_list(normalized_insights.get("recommendation_items"))
        if isinstance(item, dict) and str(item.get("title") or "").strip()
    ]

    manifest_path = Path(str(metadata.get("persist_manifest_path", "")).strip())
    if manifest_path.exists():
        try:
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest_payload = {}
        if isinstance(manifest_payload, dict):
            artifacts_payload = manifest_payload.get("artifacts", {})
            if not isinstance(artifacts_payload, dict):
                artifacts_payload = {}
            artifacts_payload["second_level_analysis_json"] = str(json_path)
            artifacts_payload["second_level_analysis_md"] = str(md_path)
            manifest_payload["artifacts"] = artifacts_payload
            manifest_path.write_text(
                json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    return state
