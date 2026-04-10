"""Nodo/agente RF16 de segundo nivel (comparación inter-runs + recomendaciones)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...storage.runs_comparison import (
    build_comparison_markdown,
    compare_runs,
    pick_latest_run_ids_by_process_family,
)
from ..llm_runtime import call_openai_json, resolve_node_runtime_target
from ..state import GraphState
from .alpha_runtime import load_node_prompt, record_graph_node_model_config, run_alpha_loop_for_node
from .common import annotate_node_llm_mode
from .persist_utils import write_json

_run_alpha_loop_for_node = run_alpha_loop_for_node


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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
    required_text = ("executive_summary",)
    for field in required_text:
        if not str(output.get(field, "")).strip():
            return {"passed": False, "errors": [f"campo requerido vacío: {field}"]}
    required_lists = ("audit_procedures", "recommended_tests", "next_actions")
    for field in required_lists:
        if not isinstance(output.get(field, []), list):
            return {"passed": False, "errors": [f"campo requerido debe ser lista: {field}"]}
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
    executive_summary = (
        "Comparación RF16 completada con base determinista. "
        f"Tipologías comunes detectadas: {', '.join(common_types) if common_types else 'ninguna'}."
    )
    return {
        "executive_summary": executive_summary,
        "cross_process_conclusions": [
            f"runs_count={int(deterministic_payload.get('runs_count', 0) or 0)}",
            f"common_fraud_types={common_types}",
        ],
        "audit_procedures": procedures[:6],
        "recommended_tests": tests[:8],
        "next_actions": actions[:8],
    }


def _build_second_level_markdown(*, deterministic_payload: dict[str, Any], llm_insights: dict[str, Any]) -> str:
    base = build_comparison_markdown(deterministic_payload).rstrip()
    lines = [base, "", "## Conclusiones LLM (Agente 2º nivel)", ""]
    lines.append(f"- executive_summary: {str(llm_insights.get('executive_summary', '')).strip()}")
    lines.append("- cross_process_conclusions:")
    for row in _safe_list(llm_insights.get("cross_process_conclusions"))[:8]:
        lines.append(f"  - {str(row).strip()}")
    lines.append("- audit_procedures:")
    for row in _safe_list(llm_insights.get("audit_procedures"))[:8]:
        lines.append(f"  - {str(row).strip()}")
    lines.append("- recommended_tests:")
    for row in _safe_list(llm_insights.get("recommended_tests"))[:12]:
        lines.append(f"  - {str(row).strip()}")
    lines.append("- next_actions:")
    for row in _safe_list(llm_insights.get("next_actions"))[:12]:
        lines.append(f"  - {str(row).strip()}")
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

    fallback_insights = _fallback_llm_insights(deterministic_payload=deterministic_payload)
    prompt_info = load_node_prompt(
        node_id="second_level_explainer",
        fallback_text=(
            "Actúa como auditor senior. Analiza la comparación de runs y devuelve SOLO JSON con: "
            "executive_summary, cross_process_conclusions[], audit_procedures[], recommended_tests[], next_actions[]."
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
        output = dict(fallback_insights)
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
        return output

    input_payload = {
        "deterministic_comparison": deterministic_payload,
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

    next_actions = [str(item).strip() for item in _safe_list(llm_insights.get("next_actions")) if str(item).strip()]
    state.recomendaciones = [{"source": "rf16_second_level", "action": row} for row in next_actions]

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
