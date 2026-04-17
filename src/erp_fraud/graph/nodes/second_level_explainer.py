"""Nodo/agente RF16 de segundo nivel (comparación inter-runs + recomendaciones)."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

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
                        "summary": str(parsed.get("rationale") or parsed.get("summary") or "").strip(),
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


def _validate_second_level_output(output: Any, _input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {"passed": False, "errors": ["second_level output debe ser objeto"]}
    executive_summary = output.get("executive_summary")
    if executive_summary in (None, "", [], {}):
        return {"passed": False, "errors": ["campo requerido vacío: executive_summary"]}
    required_lists = ("audit_procedures", "recommended_tests", "next_actions")
    for field in required_lists:
        if not isinstance(output.get(field, []), list):
            return {"passed": False, "errors": [f"campo requerido debe ser lista: {field}"]}
    if not (
        _safe_list(output.get("audit_procedures"))
        or _safe_list(output.get("recommended_tests"))
        or _safe_list(output.get("next_actions"))
    ):
        return {"passed": False, "errors": ["el agente debe proponer al menos una acción/procedimiento/test"]}
    return {"passed": True, "errors": []}


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
    deterministic_payload = compare_runs(run_ids=run_ids, base_dir=base_dir)
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
            "recommended_tests[{test_id,rationale,priority,expected_value}], "
            "next_actions[{action,why,owner,urgency}]. "
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
                output = llm_output
        else:
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
            }
        if not isinstance(output, dict):
            output = dict(fallback_insights)
        return output

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
    }
    llm_insights = _run_alpha_loop_for_node(
        state=state,
        node_id="second_level_explainer",
        prompt_text=prompt_text,
        input_payload=input_payload,
        generate_fn=_generate,
        validators={"second_level_schema": _validate_second_level_output},
        max_iter=2,
    )
    if not isinstance(llm_insights, dict):
        llm_insights = dict(fallback_insights)

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

    metadata["second_level_explainer_status"] = "OK"
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
