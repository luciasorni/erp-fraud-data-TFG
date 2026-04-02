"""Nodo explicador y validadores de guardrails."""

from __future__ import annotations

from typing import Any

from ...catalog import load_test_specs_from_catalog
from ...config import (
    DEFAULT_BASE_DIR,
    DEFAULT_CATALOG_PATH,
    DEFAULT_EXPLAINER_KB_TOP_K,
    DEFAULT_EXPLAINER_TOP_K,
    DEFAULT_KB_CHROMA_CONFIG,
)
from .common import resolve_project_path
from .persist_utils import normalize_columns
from ..state import GraphState
from .alpha_runtime import load_node_prompt, record_graph_node_model_config, run_alpha_loop_for_node
from .common import annotate_node_llm_mode
from .finding_utils import (
    build_acfe_reference_via_kb,
    build_explanation_from_finding,
    build_explanations_for_ranked_entities,
    build_structured_explainer_feedback,
    sanitize_explanations_against_findings,
)
from .validators import validate_explanations_output
from ..llm_runtime import call_openai_json, resolve_node_runtime_target

# Compat tests: permitir monkeypatch del nombre legacy.
_run_alpha_loop_for_node = run_alpha_loop_for_node

def explainer_node(state: GraphState) -> GraphState:
    """Nodo explicador con guardrails (RF14-08)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    llm_mode = annotate_node_llm_mode(metadata=metadata, node_id="expert_explainer")
    runtime_target = resolve_node_runtime_target(
        node_id="expert_explainer",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
    )
    record_graph_node_model_config(
        node_id="expert_explainer",
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
    findings = [row for row in state.findings if isinstance(row, dict)]

    if not findings:
        state.explanations = [
            {
                "test_id": "",
                "cited_test_id": "",
                "status": "NO_DATA",
                "fraud_type": "",
                "finding_count": 0,
                "referenced_columns": [],
                "cited_keys": {},
                "cited_evidence_columns": [],
                "sample_entity_key": "",
                "summary": "No hay resultados de ejecución para explicar.",
                "source": "explainer_stub_guarded",
            }
        ]
        metadata["explainer_status"] = "NO_FINDINGS"
        metadata["explainer_explanations_count"] = 1
        return state

    kb_enabled = bool(metadata.get("kb_search_enabled", False))
    kb_top_k = int(metadata.get("explainer_kb_top_k", DEFAULT_EXPLAINER_KB_TOP_K) or DEFAULT_EXPLAINER_KB_TOP_K)
    if kb_top_k <= 0:
        kb_top_k = DEFAULT_EXPLAINER_KB_TOP_K
    explainer_top_k = int(metadata.get("explainer_top_k", DEFAULT_EXPLAINER_TOP_K) or DEFAULT_EXPLAINER_TOP_K)
    if explainer_top_k <= 0:
        explainer_top_k = DEFAULT_EXPLAINER_TOP_K
    kb_chroma_config_path = resolve_project_path(
        str(metadata.get("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)).strip() or DEFAULT_KB_CHROMA_CONFIG
    )
    base_dir = resolve_project_path(str(metadata.get("base_dir", DEFAULT_BASE_DIR)).strip() or DEFAULT_BASE_DIR)
    catalog_path = resolve_project_path(
        str(metadata.get("catalog_path", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
    )

    catalog_test_ids: set[str] = set()
    try:
        catalog_specs = load_test_specs_from_catalog(catalog_path=catalog_path, validate_schema=True)
        for spec in catalog_specs:
            if not isinstance(spec, dict):
                continue
            test_id = str(spec.get("id", "")).strip()
            if test_id:
                catalog_test_ids.add(test_id)
    except Exception:
        catalog_test_ids = set()

    schema_columns: set[str] = set()
    schema_payload = state.schema if isinstance(state.schema, dict) else {}
    tables = schema_payload.get("tables", []) if isinstance(schema_payload.get("tables"), list) else []
    for table in tables:
        if not isinstance(table, dict):
            continue
        columns = table.get("columns", [])
        if not isinstance(columns, list):
            continue
        for col in columns:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name", col.get("column_name", ""))).strip()
            if name:
                schema_columns.add(name)

    ranked_explanations = build_explanations_for_ranked_entities(
        findings=findings,
        ranking=[row for row in state.ranking if isinstance(row, dict)],
        top_k=explainer_top_k,
    )
    seed_explanations = ranked_explanations if ranked_explanations else [
        build_explanation_from_finding(row) for row in findings
    ]

    explanations = []
    for item in seed_explanations:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        test_id = str(item.get("test_id", "")).strip()
        fraud_type = str(item.get("fraud_type", "")).strip()
        acfe_query = (
            f"ACFE anti-fraud data analytics test {test_id} {fraud_type} "
            f"evidence columns {' '.join(item.get('cited_evidence_columns', []))}"
        ).strip()
        item["acfe_reference"] = build_acfe_reference_via_kb(
            kb_enabled=kb_enabled,
            kb_query=acfe_query,
            kb_top_k=kb_top_k,
            kb_chroma_config_path=kb_chroma_config_path,
            base_dir=base_dir,
        )
        explanations.append(item)

    simulate_hallucination_once = bool(metadata.get("explainer_simulate_hallucination_once", False))
    prompt_info = load_node_prompt(
        node_id="expert_explainer",
        fallback_text="Genera explicación auditora con evidencia real sin alucinaciones.",
        registry_path=metadata.get("prompt_registry_path"),
    )
    metadata["explainer_prompt_path"] = str(prompt_info.get("path", "")).strip()
    metadata["explainer_prompt_version"] = str(prompt_info.get("version", "")).strip()
    metadata["explainer_prompt_hash"] = str(prompt_info.get("hash", "")).strip()
    metadata["explainer_prompt_status"] = str(prompt_info.get("status", "")).strip()
    prompt_text = str(prompt_info.get("text", ""))
    runtime_by_node = metadata.setdefault("llm_runtime_by_node", {})
    if not isinstance(runtime_by_node, dict):
        runtime_by_node = {}
        metadata["llm_runtime_by_node"] = runtime_by_node

    def _generate_explanations(
        _prompt: str,
        input_payload: dict[str, Any],
        repair_feedback: list[str],
        iteration: int,
    ) -> list[dict[str, Any]]:
        base = [dict(row) for row in explanations if isinstance(row, dict)]
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
            metadata["explainer_llm_call_status"] = str(llm_meta.get("status", "ERROR")).strip()
            runtime_by_node["expert_explainer"] = {
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
            if isinstance(llm_output, list):
                base = [row for row in llm_output if isinstance(row, dict)]
        else:
            metadata["explainer_llm_call_status"] = "SKIPPED"
            runtime_by_node["expert_explainer"] = {
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
        if iteration == 1 and not repair_feedback and simulate_hallucination_once and base:
            base[0]["referenced_columns"] = list(normalize_columns(base[0].get("referenced_columns", []))) + [
                "NO_EXISTE_COL"
            ]
            base[0]["cited_keys"] = {"NO_KEY": "X"}
            base[0]["cited_evidence_columns"] = list(
                normalize_columns(base[0].get("cited_evidence_columns", []))
            ) + ["NO_EVIDENCE"]
            return base
        if repair_feedback:
            findings_payload = input_payload.get("findings", [])
            if isinstance(findings_payload, list):
                metadata["explainer_last_repair_feedback"] = build_structured_explainer_feedback(repair_feedback)
                return sanitize_explanations_against_findings(
                    explanations=base,
                    findings=[row for row in findings_payload if isinstance(row, dict)],
                )
        return base

    explainer_input_payload = {
        "findings": findings,
        "catalog_test_ids": sorted(catalog_test_ids),
        "schema_columns": sorted(schema_columns),
    }
    try:
        state.explanations = _run_alpha_loop_for_node(
            state=state,
            node_id="expert_explainer",
            prompt_text=prompt_text,
            input_payload=explainer_input_payload,
            generate_fn=_generate_explanations,
            validators={"explanations_guardrails": validate_explanations_output},
            max_iter=2,
        )
    except Exception as exc:
        state.explanations = [dict(row) for row in explanations if isinstance(row, dict)]
        metadata["explainer_fallback_used"] = True
        metadata["explainer_fallback_reason"] = f"{type(exc).__name__}: {exc}"
    metadata["explainer_status"] = "OK"
    metadata["explainer_explanations_count"] = len(state.explanations)
    metadata["explainer_run_summary"] = {
        "findings_count": len(findings),
        "ranking_available": bool(state.ranking),
        "explainer_top_k": explainer_top_k,
        "entities_explained": sorted(
            {
                str(row.get("sample_entity_key", "")).strip()
                for row in state.explanations
                if isinstance(row, dict) and str(row.get("sample_entity_key", "")).strip()
            }
        ),
    }
    metadata["explainer_guardrails"] = [
        "test_id debe existir en findings ejecutados",
        "cited_test_id debe coincidir con test_id",
        "cited_keys debe ser subconjunto de row.keys",
        "cited_evidence_columns debe ser subconjunto de row.evidence_columns",
        "referenced_columns debe ser subconjunto de result.columns",
    ]
    metadata["explainer_kb_enabled"] = kb_enabled
    if "explainer_last_repair_feedback" not in metadata:
        metadata["explainer_last_repair_feedback"] = []
    return state

def expert_explainer_node(state: GraphState) -> GraphState:
    """Alias semántico AG03-09 para el nodo LLM explicador."""
    return explainer_node(state)

def _validate_explanations_guardrails(
    *,
    explanations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    catalog_test_ids: set[str] | None = None,
    schema_columns: set[str] | None = None,
) -> None:
    catalog_allowlist = catalog_test_ids or set()
    allowed_schema_columns = {str(name).strip().lower() for name in (schema_columns or set()) if str(name).strip()}
    findings_by_test: dict[str, dict[str, Any]] = {}
    for row in findings:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id", "")).strip()
        if test_id:
            findings_by_test[test_id] = row

    for idx, item in enumerate(explanations):
        if not isinstance(item, dict):
            raise ValueError(f"explanations[{idx}] inválida: debe ser objeto")
        test_id = str(item.get("test_id", "")).strip()
        if not test_id:
            raise ValueError(f"explanations[{idx}] inválida: test_id vacío")
        if catalog_allowlist and test_id not in catalog_allowlist:
            raise ValueError(f"Guardrail: explicación referencia test_id fuera de catálogo: {test_id}")
        if test_id not in findings_by_test:
            raise ValueError(f"Guardrail: explicación referencia test_id no ejecutado: {test_id}")
        cited_test_id = str(item.get("cited_test_id", "")).strip()
        if cited_test_id != test_id:
            raise ValueError(
                f"Guardrail: explicación {test_id} debe citar el mismo test_id en cited_test_id"
            )

        allowed_columns = set(normalize_columns(findings_by_test[test_id].get("columns", [])))
        referenced = normalize_columns(item.get("referenced_columns", []))
        unknown = [col for col in referenced if col not in allowed_columns]
        if unknown:
            raise ValueError(
                f"Guardrail: explicación {test_id} referencia columnas no presentes en resultado: {unknown}"
            )
        rows = findings_by_test[test_id].get("rows", [])
        first_row = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
        allowed_keys = first_row.get("keys", {}) if isinstance(first_row, dict) else {}
        if not isinstance(allowed_keys, dict):
            allowed_keys = {}
        cited_keys = item.get("cited_keys", {})
        if not isinstance(cited_keys, dict):
            raise ValueError(f"Guardrail: explicación {test_id} debe incluir cited_keys (dict)")
        unknown_key_names = [name for name in cited_keys.keys() if name not in allowed_keys]
        if unknown_key_names:
            raise ValueError(
                f"Guardrail: explicación {test_id} cita keys inexistentes en finding: {unknown_key_names}"
            )
        if allowed_schema_columns:
            unknown_schema_keys = [
                name for name in cited_keys.keys() if str(name).strip().lower() not in allowed_schema_columns
            ]
            if unknown_schema_keys:
                raise ValueError(
                    f"Guardrail: explicación {test_id} cita keys fuera de schema_summary: {unknown_schema_keys}"
                )
        allowed_evidence = []
        maybe_evidence = first_row.get("evidence_columns", []) if isinstance(first_row, dict) else []
        if isinstance(maybe_evidence, list):
            allowed_evidence = normalize_columns(maybe_evidence)
        cited_evidence = normalize_columns(item.get("cited_evidence_columns", []))
        if cited_evidence:
            unknown_evidence = [col for col in cited_evidence if col not in set(allowed_evidence)]
            if unknown_evidence:
                raise ValueError(
                    f"Guardrail: explicación {test_id} cita evidence_columns no presentes: {unknown_evidence}"
                )
