"""Nodos de planificación (hipótesis/tests) y validadores."""

from __future__ import annotations

from typing import Any

from ...agents.policy_enforcer import PolicyEnforcer, ToolPolicyDeniedError
from ...config import (
    DEFAULT_BASE_DIR,
    DEFAULT_CATALOG_PATH,
    DEFAULT_HYPOTHESIS_KB_TOP_K,
    DEFAULT_HYPOTHESIS_MAX_ITEMS,
    DEFAULT_KB_CHROMA_CONFIG,
    DEFAULT_TEST_PLANNER_TOP_N,
)
from .common import resolve_project_path
from ..state import GraphState
from . import deps
from .alpha_runtime import load_node_prompt, record_graph_node_model_config, run_alpha_loop_for_node
from .common import annotate_node_llm_mode
from .finding_utils import (
    build_hypotheses_from_tools,
    build_schema_columns_lookup,
    score_test_against_hypothesis,
    test_spec_is_schema_compatible,
)
from .tooling import (
    build_graph_policy_enforcer,
    tool_data_catalog,
    tool_runstore_write_stub,
    tool_schema,
    tool_test_catalog,
)
from .validators import validate_hypotheses_output, validate_selected_tests_output
from ..llm_runtime import call_openai_json, resolve_node_runtime_target
from ..fraud_taxonomy import branch_for_fraud_type, load_fraud_taxonomy

# Compat tests: permitir monkeypatch del nombre legacy.
_run_alpha_loop_for_node = run_alpha_loop_for_node


def _normalize_llm_hypotheses_output(
    *,
    llm_output: Any,
    default_hypotheses: list[dict[str, Any]],
    catalog_tests: list[dict[str, Any]],
    max_hypotheses: int,
) -> list[dict[str, Any]]:
    if isinstance(llm_output, list):
        return [row for row in llm_output if isinstance(row, dict)]
    if not isinstance(llm_output, dict):
        return []

    decisions = llm_output.get("decisions", [])
    if not isinstance(decisions, list):
        return []

    by_fraud_type: dict[str, dict[str, Any]] = {}
    for row in default_hypotheses:
        if not isinstance(row, dict):
            continue
        key = str(row.get("fraud_type", "")).strip()
        if key and key not in by_fraud_type:
            by_fraud_type[key] = row

    catalog_tests_by_fraud_type: dict[str, list[str]] = {}
    for spec in catalog_tests:
        if not isinstance(spec, dict):
            continue
        fraud_type = str(spec.get("fraud_type", "")).strip()
        test_id = str(spec.get("id", "")).strip()
        if not fraud_type or not test_id:
            continue
        bucket = catalog_tests_by_fraud_type.setdefault(fraud_type, [])
        if test_id not in bucket:
            bucket.append(test_id)

    out: list[dict[str, Any]] = []
    seen_fraud_type: set[str] = set()
    for idx, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            continue
        fraud_type = str(decision.get("fraud_type", "")).strip()
        if not fraud_type or fraud_type in seen_fraud_type:
            continue
        seed = by_fraud_type.get(fraud_type)
        if not isinstance(seed, dict):
            continue
        seen_fraud_type.add(fraud_type)
        hypothesis_id = str(decision.get("id", "")).strip() or f"HYP-{idx + 1:03d}"
        reason = str(decision.get("reason", "")).strip()
        row = dict(seed)
        row["hypothesis_id"] = hypothesis_id
        row["fraud_type"] = fraud_type
        if str(decision.get("process_step", "")).strip():
            row["process_step"] = str(decision.get("process_step", "")).strip()
        row["candidate_test_ids"] = catalog_tests_by_fraud_type.get(fraud_type, row.get("candidate_test_ids", []))[:3]
        if reason:
            row["description"] = reason
            row["title"] = f"Hypothesis for {fraud_type.replace('_', ' ').title()} ({reason[:64]})"
        out.append(row)
        if len(out) >= max_hypotheses:
            break
    return out


def _normalize_llm_selected_tests_output(
    *,
    llm_output: Any,
    allowlist_ids: set[str],
    default_hypothesis_id: str,
    hypotheses_by_id: dict[str, dict[str, Any]],
    test_meta_by_id: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    if isinstance(llm_output, list):
        return [row for row in llm_output if isinstance(row, dict)]
    if not isinstance(llm_output, dict):
        return []
    decisions = llm_output.get("decisions", [])
    if not isinstance(decisions, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _resolve_hypothesis_id_from_decision(decision: dict[str, Any], test_id: str) -> str:
        explicit = str(decision.get("hypothesis_id", "")).strip()
        if explicit and explicit in hypotheses_by_id:
            return explicit
        fraud_type = str(decision.get("fraud_type", "")).strip()
        process_step = str(decision.get("process_step", "")).strip()
        test_meta = test_meta_by_id.get(test_id, {})
        if not fraud_type:
            fraud_type = str(test_meta.get("fraud_type", "")).strip()
        if not process_step:
            process_step = str(test_meta.get("process_step", "")).strip()
        if fraud_type:
            for hyp_id, hyp in hypotheses_by_id.items():
                if str(hyp.get("fraud_type", "")).strip() == fraud_type:
                    if process_step and str(hyp.get("process_step", "")).strip() not in {"", process_step}:
                        continue
                    return hyp_id
        if process_step:
            for hyp_id, hyp in hypotheses_by_id.items():
                if str(hyp.get("process_step", "")).strip() == process_step:
                    return hyp_id
        return explicit or default_hypothesis_id

    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        test_id = str(decision.get("id", "")).strip()
        if not test_id or (allowlist_ids and test_id not in allowlist_ids):
            continue
        hypothesis_id = _resolve_hypothesis_id_from_decision(decision, test_id)
        reason = str(decision.get("reason", "")).strip()
        key = (hypothesis_id, test_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "hypothesis_id": hypothesis_id,
                "test_id": test_id,
                "source": "planner_llm",
                "score": 0,
                "match_reasons": [reason] if reason else ["llm_decision"],
            }
        )
    return out

def hypothesis_planner_node(state: GraphState) -> GraphState:
    """Genera hipótesis con trazabilidad de fuentes (RF15c-03)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    llm_mode = annotate_node_llm_mode(metadata=metadata, node_id="hypothesis_planner")
    runtime_target = resolve_node_runtime_target(
        node_id="hypothesis_planner",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
    )
    record_graph_node_model_config(
        node_id="hypothesis_planner",
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
    agent_id = str(metadata.get("graph_agent_id", "expert_recommender")).strip() or "expert_recommender"
    node_id = "hypothesis_planner"
    catalog_path = resolve_project_path(
        str(metadata.get("catalog_path", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
    )
    data_dictionary_path = resolve_project_path(
        str(metadata.get("data_dictionary_path", "data_dictionary.json")).strip() or "data_dictionary.json"
    )
    kb_search_enabled = bool(metadata.get("kb_search_enabled", False))
    kb_top_k = int(metadata.get("hypothesis_kb_top_k", DEFAULT_HYPOTHESIS_KB_TOP_K) or DEFAULT_HYPOTHESIS_KB_TOP_K)
    if kb_top_k <= 0:
        kb_top_k = 3
    max_hypotheses = int(metadata.get("hypothesis_max_items", DEFAULT_HYPOTHESIS_MAX_ITEMS) or DEFAULT_HYPOTHESIS_MAX_ITEMS)
    if max_hypotheses <= 0:
        max_hypotheses = 1

    enforcer: PolicyEnforcer | None = None
    catalog_out: dict[str, Any] = {"tests": [], "count": 0}
    schema_out: dict[str, Any] = {"payload": {"table_names": [], "count": 0, "columns_by_table": {}}}
    data_catalog_out: dict[str, Any] = {"payload": {"entries": [], "count": 0, "status": "MISSING"}}
    try:
        enforcer = build_graph_policy_enforcer(state)
        catalog_out = enforcer.enforce_and_call(
            agent_id=agent_id,
            tool_id="TestCatalog",
            tool_callable=tool_test_catalog,
            node_id=node_id,
            catalog_path=catalog_path,
        )
        schema_out = enforcer.enforce_and_call(
            agent_id=agent_id,
            tool_id="Schema",
            tool_callable=lambda: tool_schema(state),
            node_id=node_id,
        )
        data_catalog_out = enforcer.enforce_and_call(
            agent_id=agent_id,
            tool_id="DataCatalog",
            tool_callable=tool_data_catalog,
            node_id=node_id,
            data_dictionary_path=data_dictionary_path,
        )
        metadata["hypothesis_tooling_status"] = "OK"
    except Exception as exc:
        # RF14 stub mode: nunca bloquear planificación por problemas de policy/config en CI.
        metadata["hypothesis_tooling_status"] = f"ERROR: {type(exc).__name__}: {exc}"
    catalog_tests = catalog_out.get("tests", []) if isinstance(catalog_out, dict) else []
    if not isinstance(catalog_tests, list):
        catalog_tests = []
    allowed_fraud_types = sorted(
        {
            str(row.get("fraud_type", "")).strip()
            for row in catalog_tests
            if isinstance(row, dict) and str(row.get("fraud_type", "")).strip()
        }
    )
    allowed_process_steps = sorted(
        {
            str(row.get("process_step", "")).strip()
            for row in catalog_tests
            if isinstance(row, dict) and str(row.get("process_step", "")).strip()
        }
    )
    if llm_mode == "real":
        min_hypotheses_target = min(max_hypotheses, 2 if len(allowed_fraud_types) >= 2 else 1)
        min_distinct_fraud_types = min(2, len(allowed_fraud_types)) if allowed_fraud_types else 1
    else:
        min_hypotheses_target = 1
        min_distinct_fraud_types = 1
    metadata["hypothesis_max_items"] = max_hypotheses
    metadata["hypothesis_min_items_target"] = min_hypotheses_target
    metadata["hypothesis_min_distinct_fraud_types"] = min_distinct_fraud_types
    schema_columns_by_table = {}
    schema_payload = schema_out.get("payload", {}) if isinstance(schema_out, dict) else {}
    if isinstance(schema_payload, dict):
        raw = schema_payload.get("columns_by_table", {})
        if isinstance(raw, dict):
            schema_columns_by_table = {
                str(table).strip(): [
                    str(col).strip() for col in cols if str(col).strip()
                ]
                for table, cols in raw.items()
                if str(table).strip() and isinstance(cols, list)
            }

    kb_hits: list[dict[str, Any]] = []
    kb_status = "SKIPPED"
    kb_query = str(metadata.get("hypothesis_query", "split payments authorization threshold")).strip()
    if kb_search_enabled:
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
            kb_out = tool.search(query=kb_query, top_k=kb_top_k)
            hits = kb_out.get("hits", []) if isinstance(kb_out, dict) else []
            kb_hits = [row for row in hits if isinstance(row, dict)]
            kb_status = "OK"
        except Exception as exc:
            kb_status = f"ERROR:{type(exc).__name__}"

    if not state.hypotheses:
        prompt_info = load_node_prompt(
            node_id="hypothesis_planner",
            fallback_text=(
                "Genera hipótesis iniciales P2P con sources trazables usando TestCatalog, "
                "Schema/DataCatalog y KB opcional."
            ),
            registry_path=metadata.get("prompt_registry_path"),
        )
        metadata["hypothesis_prompt_path"] = str(prompt_info.get("path", "")).strip()
        metadata["hypothesis_prompt_version"] = str(prompt_info.get("version", "")).strip()
        metadata["hypothesis_prompt_hash"] = str(prompt_info.get("hash", "")).strip()
        metadata["hypothesis_prompt_status"] = str(prompt_info.get("status", "")).strip()
        default_hypotheses = build_hypotheses_from_tools(
            catalog_out=catalog_out,
            schema_out=schema_out,
            data_catalog_out=data_catalog_out,
            kb_status=kb_status,
            kb_query=kb_query,
            kb_top_k=kb_top_k,
            kb_hits=kb_hits,
            max_hypotheses=max_hypotheses,
        )
        prompt_text = str(prompt_info.get("text", ""))

        runtime_by_node = metadata.setdefault("llm_runtime_by_node", {})
        if not isinstance(runtime_by_node, dict):
            runtime_by_node = {}
            metadata["llm_runtime_by_node"] = runtime_by_node

        def _generate_hypotheses(
            _prompt: str,
            _input_payload: dict[str, Any],
            repair_feedback: list[str],
            _iteration: int,
        ) -> list[dict[str, Any]]:
            fallback = list(default_hypotheses)
            if not bool(runtime_target.get("enabled", False)):
                metadata["hypothesis_llm_call_status"] = "SKIPPED"
                runtime_by_node["hypothesis_planner"] = {
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
                return fallback
            llm_output, llm_meta = call_openai_json(
                model_used=str(runtime_target.get("model_used", "")).strip() or "gpt-5.4-mini",
                temperature=float(runtime_target.get("temperature", 0.0) or 0.0),
                max_tokens=int(runtime_target.get("max_tokens", 0) or 0),
                prompt_text=prompt_text,
                input_payload=_input_payload,
                repair_feedback=repair_feedback,
                timeout_s=float(metadata.get("llm_timeout_s", 30.0) or 30.0),
                max_retries=int(metadata.get("llm_max_retries", 1) or 1),
                retry_backoff_s=float(metadata.get("llm_retry_backoff_s", 0.6) or 0.6),
            )
            metadata["hypothesis_llm_call_status"] = str(llm_meta.get("status", "ERROR")).strip()
            runtime_by_node["hypothesis_planner"] = {
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
            parsed = _normalize_llm_hypotheses_output(
                llm_output=llm_output,
                default_hypotheses=fallback,
                catalog_tests=[row for row in catalog_tests if isinstance(row, dict)],
                max_hypotheses=max_hypotheses,
            )
            if parsed:
                return parsed
            return fallback

        hypothesis_input_payload = {
            "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
            "schema_tables_count": int(schema_out.get("payload", {}).get("count", 0) or 0),
            "data_catalog_fields_count": int(data_catalog_out.get("payload", {}).get("count", 0) or 0),
            "kb_search_status": kb_status,
            "kb_hits_count": len(kb_hits),
            "kb_top_k": kb_top_k,
            "allowed_fraud_types": allowed_fraud_types,
            "allowed_process_steps": allowed_process_steps,
            "schema_columns_by_table": schema_columns_by_table,
            "max_hypotheses": max_hypotheses,
            "min_hypotheses": min_hypotheses_target,
            "min_distinct_fraud_types": min_distinct_fraud_types,
        }
        try:
            state.hypotheses = _run_alpha_loop_for_node(
                state=state,
                node_id="hypothesis_planner",
                prompt_text=prompt_text,
                input_payload=hypothesis_input_payload,
                generate_fn=_generate_hypotheses,
                validators={"hypothesis_schema": validate_hypotheses_output},
                max_iter=2,
            )
        except Exception as exc:
            state.hypotheses = list(default_hypotheses)
            metadata["hypothesis_fallback_used"] = True
            metadata["hypothesis_fallback_reason"] = f"{type(exc).__name__}: {exc}"

    fraud_taxonomy = load_fraud_taxonomy(
        config_path=str(metadata.get("fraud_taxonomy_config", "")).strip() or None
    )
    fraud_source = str((fraud_taxonomy.get("source", {}) or {}).get("document", "")).strip()
    branches = fraud_taxonomy.get("branches", []) if isinstance(fraud_taxonomy.get("branches"), list) else []
    metadata["fraud_taxonomy_config_path"] = str(fraud_taxonomy.get("config_path", "")).strip()
    metadata["fraud_taxonomy_source_document"] = fraud_source
    metadata["fraud_taxonomy_branches_count"] = len([row for row in branches if isinstance(row, dict)])
    for item in state.hypotheses:
        if not isinstance(item, dict):
            continue
        fraud_type = str(item.get("fraud_type", "")).strip()
        branch = branch_for_fraud_type(fraud_type=fraud_type, taxonomy=fraud_taxonomy)
        item["fraud_tree_branch"] = branch["id"]
        item["fraud_tree_branch_label"] = branch["label"]
        if fraud_source:
            item["fraud_tree_source_document"] = fraud_source

    if enforcer is None:
        metadata["hypothesis_runstore_status"] = "SKIPPED_NO_ENFORCER"
    else:
        try:
            runstore_out = enforcer.enforce_and_call(
                agent_id=agent_id,
                tool_id="RunStore",
                tool_callable=tool_runstore_write_stub,
                node_id=node_id,
                run_id=str(state.run_id),
                hypotheses=state.hypotheses,
            )
            metadata["hypothesis_runstore_status"] = str(runstore_out.get("status", "UNKNOWN"))
        except ToolPolicyDeniedError:
            metadata["hypothesis_runstore_status"] = "DENIED"
        except Exception as exc:
            metadata["hypothesis_runstore_status"] = f"ERROR: {type(exc).__name__}: {exc}"

    return state

def test_planner_node(state: GraphState) -> GraphState:
    """Selecciona test_ids allowlist del catálogo para cada hipótesis (RF14-06/RF15c-05)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    llm_mode = annotate_node_llm_mode(metadata=metadata, node_id="test_planner")
    runtime_target = resolve_node_runtime_target(
        node_id="test_planner",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
    )
    record_graph_node_model_config(
        node_id="test_planner",
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
    agent_id = str(metadata.get("graph_test_planner_agent_id", "expert_recommender")).strip()
    agent_id = agent_id or "expert_recommender"
    node_id = "test_planner"
    catalog_path = resolve_project_path(
        str(metadata.get("catalog_path", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
    )
    top_n = int(metadata.get("test_planner_top_n", DEFAULT_TEST_PLANNER_TOP_N) or DEFAULT_TEST_PLANNER_TOP_N)
    if top_n <= 0:
        top_n = 1

    catalog_out: dict[str, Any] = {"tests": [], "count": 0}
    try:
        enforcer = build_graph_policy_enforcer(state)
        catalog_out = enforcer.enforce_and_call(
            agent_id=agent_id,
            tool_id="TestCatalog",
            tool_callable=tool_test_catalog,
            node_id=node_id,
            catalog_path=catalog_path,
        )
        metadata["test_planner_tooling_status"] = "OK"
    except Exception as exc:
        metadata["test_planner_tooling_status"] = f"ERROR: {type(exc).__name__}: {exc}"
        try:
            catalog_out = tool_test_catalog(catalog_path=catalog_path)
            metadata["test_planner_tooling_fallback"] = "DIRECT_CATALOG"
        except Exception as inner_exc:
            metadata["test_planner_tooling_fallback"] = f"ERROR: {type(inner_exc).__name__}: {inner_exc}"
            catalog_out = {"tests": [], "count": 0}
    catalog_tests = catalog_out.get("tests", []) if isinstance(catalog_out, dict) else []
    if not isinstance(catalog_tests, list):
        catalog_tests = []
    schema_lookup = build_schema_columns_lookup(state.schema if isinstance(state.schema, dict) else {})
    compatible_catalog_tests: list[dict[str, Any]] = []
    filtered_out: list[str] = []
    if not schema_lookup:
        compatible_catalog_tests = [row for row in catalog_tests if isinstance(row, dict)]
    else:
        for test_spec in catalog_tests:
            if not isinstance(test_spec, dict):
                continue
            compatible, reason = test_spec_is_schema_compatible(
                test_spec=test_spec,
                schema_columns_lookup=schema_lookup,
            )
            if compatible:
                compatible_catalog_tests.append(test_spec)
            else:
                filtered_out.append(reason)
    allowlist_ids = {
        str(row.get("id", "")).strip()
        for row in compatible_catalog_tests
        if isinstance(row, dict) and str(row.get("id", "")).strip()
    }
    hypotheses_by_id: dict[str, dict[str, Any]] = {}
    for idx, hypothesis in enumerate(state.hypotheses):
        if not isinstance(hypothesis, dict):
            continue
        hypothesis_id = str(hypothesis.get("hypothesis_id", f"HYP-{idx + 1:03d}")).strip()
        if hypothesis_id:
            hypotheses_by_id[hypothesis_id] = hypothesis
    test_meta_by_id: dict[str, dict[str, str]] = {}
    for row in compatible_catalog_tests:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("id", "")).strip()
        if not test_id:
            continue
        test_meta_by_id[test_id] = {
            "fraud_type": str(row.get("fraud_type", "")).strip(),
            "process_step": str(row.get("process_step", "")).strip(),
        }

    selected_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for idx, hypothesis in enumerate(state.hypotheses):
        if not isinstance(hypothesis, dict):
            continue
        hypothesis_id = str(hypothesis.get("hypothesis_id", f"HYP-{idx + 1:03d}")).strip()
        hypothesis_text = (
            f"{hypothesis.get('title', '')} {hypothesis.get('description', '')} "
            f"{hypothesis.get('fraud_type', '')}"
        ).strip()

        requested_candidates = hypothesis.get("candidate_test_ids", [])
        requested_allowlist = {
            str(test_id).strip()
            for test_id in (requested_candidates if isinstance(requested_candidates, list) else [])
            if str(test_id).strip() in allowlist_ids
        }

        scored: list[tuple[int, dict[str, Any], list[str]]] = []
        for test_spec in compatible_catalog_tests:
            if not isinstance(test_spec, dict):
                continue
            test_id = str(test_spec.get("id", "")).strip()
            if not test_id:
                continue
            if requested_allowlist and test_id not in requested_allowlist:
                continue
            score, reasons = score_test_against_hypothesis(
                hypothesis_text=hypothesis_text,
                test_spec=test_spec,
            )
            if score <= 0 and not requested_allowlist:
                continue
            scored.append((score, test_spec, reasons))

        scored.sort(
            key=lambda item: (
                -int(item[0]),
                str(item[1].get("id", "")),
            )
        )
        for score, test_spec, reasons in scored[:top_n]:
            test_id = str(test_spec.get("id", "")).strip()
            key = (hypothesis_id, test_id)
            if key in seen:
                continue
            seen.add(key)
            selected_rows.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "test_id": test_id,
                    "source": "planner_allowlist_heuristic",
                    "score": int(score),
                    "match_reasons": reasons,
                }
            )

    if not selected_rows and allowlist_ids:
        # Fallback seguro: primer test de catálogo para mantener continuidad del grafo.
        fallback_test_id = sorted(allowlist_ids)[0]
        fallback_hypothesis_id = (
            str(state.hypotheses[0].get("hypothesis_id", "HYP-001"))
            if state.hypotheses and isinstance(state.hypotheses[0], dict)
            else "HYP-001"
        )
        selected_rows.append(
            {
                "hypothesis_id": fallback_hypothesis_id,
                "test_id": fallback_test_id,
                "source": "planner_fallback_first_catalog_test",
                "score": 0,
                "match_reasons": ["fallback_first_catalog_test"],
            }
        )

    prompt_info = load_node_prompt(
        node_id="test_planner",
        fallback_text="Selecciona tests allowlist del catálogo para cada hipótesis.",
        registry_path=metadata.get("prompt_registry_path"),
    )
    metadata["test_planner_prompt_path"] = str(prompt_info.get("path", "")).strip()
    metadata["test_planner_prompt_version"] = str(prompt_info.get("version", "")).strip()
    metadata["test_planner_prompt_hash"] = str(prompt_info.get("hash", "")).strip()
    metadata["test_planner_prompt_status"] = str(prompt_info.get("status", "")).strip()

    prompt_text = str(prompt_info.get("text", ""))

    runtime_by_node = metadata.setdefault("llm_runtime_by_node", {})
    if not isinstance(runtime_by_node, dict):
        runtime_by_node = {}
        metadata["llm_runtime_by_node"] = runtime_by_node

    def _generate_selected_tests(
        _prompt: str,
        input_payload: dict[str, Any],
        repair_feedback: list[str],
        _iteration: int,
    ) -> list[dict[str, Any]]:
        fallback = list(selected_rows)
        if not bool(runtime_target.get("enabled", False)):
            metadata["test_planner_llm_call_status"] = "SKIPPED"
            runtime_by_node["test_planner"] = {
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
            return fallback
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
        metadata["test_planner_llm_call_status"] = str(llm_meta.get("status", "ERROR")).strip()
        runtime_by_node["test_planner"] = {
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
        default_hypothesis_id = (
            str(state.hypotheses[0].get("hypothesis_id", "HYP-001"))
            if state.hypotheses and isinstance(state.hypotheses[0], dict)
            else "HYP-001"
        )
        parsed = _normalize_llm_selected_tests_output(
            llm_output=llm_output,
            allowlist_ids=allowlist_ids,
            default_hypothesis_id=default_hypothesis_id,
            hypotheses_by_id=hypotheses_by_id,
            test_meta_by_id=test_meta_by_id,
        )
        if parsed:
            return parsed
        if isinstance(llm_output, list):
            return [row for row in llm_output if isinstance(row, dict)]
        return fallback

    planner_input_payload = {
        "allowlist_ids": sorted(allowlist_ids),
        "hypotheses_count": len(state.hypotheses),
        "top_n": top_n,
        "hypotheses": [
            {
                "hypothesis_id": str(row.get("hypothesis_id", "")).strip(),
                "fraud_type": str(row.get("fraud_type", "")).strip(),
                "process_step": str(row.get("process_step", "")).strip(),
                "title": str(row.get("title", "")).strip(),
                "description": str(row.get("description", "")).strip(),
                "candidate_test_ids": [
                    str(test_id).strip()
                    for test_id in row.get("candidate_test_ids", [])
                    if str(test_id).strip()
                ][:5],
            }
            for row in state.hypotheses
            if isinstance(row, dict)
        ],
        "catalog_tests": [
            {
                "test_id": str(row.get("id", "")).strip(),
                "fraud_type": str(row.get("fraud_type", "")).strip(),
                "process_step": str(row.get("process_step", "")).strip(),
                "name": str(row.get("name", "")).strip(),
            }
            for row in compatible_catalog_tests
            if isinstance(row, dict) and str(row.get("id", "")).strip()
        ],
    }
    try:
        state.selected_tests = _run_alpha_loop_for_node(
            state=state,
            node_id="test_planner",
            prompt_text=prompt_text,
            input_payload=planner_input_payload,
            generate_fn=_generate_selected_tests,
            validators={"selected_tests_schema": validate_selected_tests_output},
            max_iter=2,
        )
    except Exception as exc:
        state.selected_tests = list(selected_rows)
        metadata["test_planner_fallback_used"] = True
        metadata["test_planner_fallback_reason"] = f"{type(exc).__name__}: {exc}"

    # En modo real exigimos cobertura mínima por hipótesis para evitar concentración en una sola.
    min_per_hypothesis_real = int(metadata.get("test_planner_min_per_hypothesis_real", 1) or 1)
    if min_per_hypothesis_real < 0:
        min_per_hypothesis_real = 0
    metadata["test_planner_min_per_hypothesis_real"] = min_per_hypothesis_real
    if llm_mode == "real" and min_per_hypothesis_real > 0 and hypotheses_by_id:
        current_selected = [
            row for row in state.selected_tests if isinstance(row, dict)
        ]
        selected_pairs = {
            (
                str(row.get("hypothesis_id", "")).strip(),
                str(row.get("test_id", "")).strip(),
            )
            for row in current_selected
            if str(row.get("hypothesis_id", "")).strip() and str(row.get("test_id", "")).strip()
        }
        by_hypothesis: dict[str, int] = {}
        for hyp_id, _test_id in selected_pairs:
            by_hypothesis[hyp_id] = by_hypothesis.get(hyp_id, 0) + 1
        added_for_coverage = 0
        for hyp_id, hypothesis in hypotheses_by_id.items():
            current_count = by_hypothesis.get(hyp_id, 0)
            if current_count >= min_per_hypothesis_real:
                continue
            hypothesis_text = (
                f"{hypothesis.get('title', '')} {hypothesis.get('description', '')} "
                f"{hypothesis.get('fraud_type', '')}"
            ).strip()
            scored_candidates: list[tuple[int, str, list[str]]] = []
            requested_candidates = hypothesis.get("candidate_test_ids", [])
            requested_allowlist = {
                str(test_id).strip()
                for test_id in (requested_candidates if isinstance(requested_candidates, list) else [])
                if str(test_id).strip() in allowlist_ids
            }
            for test_spec in compatible_catalog_tests:
                if not isinstance(test_spec, dict):
                    continue
                test_id = str(test_spec.get("id", "")).strip()
                if not test_id:
                    continue
                if requested_allowlist and test_id not in requested_allowlist:
                    continue
                score, reasons = score_test_against_hypothesis(
                    hypothesis_text=hypothesis_text,
                    test_spec=test_spec,
                )
                if score <= 0 and not requested_allowlist:
                    continue
                scored_candidates.append((int(score), test_id, reasons))
            scored_candidates.sort(key=lambda item: (-item[0], item[1]))
            for score, test_id, reasons in scored_candidates:
                pair = (hyp_id, test_id)
                if pair in selected_pairs:
                    continue
                current_selected.append(
                    {
                        "hypothesis_id": hyp_id,
                        "test_id": test_id,
                        "source": "planner_real_min_coverage",
                        "score": int(score),
                        "match_reasons": reasons or ["real_min_coverage"],
                    }
                )
                selected_pairs.add(pair)
                by_hypothesis[hyp_id] = by_hypothesis.get(hyp_id, 0) + 1
                added_for_coverage += 1
                if by_hypothesis[hyp_id] >= min_per_hypothesis_real:
                    break
        state.selected_tests = current_selected
        metadata["test_planner_min_per_hypothesis_real_added"] = added_for_coverage
    state.recomendaciones = [
        {
            "hypothesis_id": str(row.get("hypothesis_id", "")).strip(),
            "test_id": str(row.get("test_id", "")).strip(),
            "reason": ", ".join(
                str(reason).strip()
                for reason in row.get("match_reasons", [])
                if str(reason).strip()
            )
            or str(row.get("source", "allowlist")).strip(),
            "source": str(row.get("source", "planner_allowlist")).strip(),
            "approved_for_execution": False,
        }
        for row in state.selected_tests
        if isinstance(row, dict)
        and str(row.get("hypothesis_id", "")).strip()
        and str(row.get("test_id", "")).strip()
    ]
    metadata["selected_tests_count"] = len(state.selected_tests)
    metadata["recommendations_count"] = len(state.recomendaciones)
    metadata["test_planner_allowlist_enforced"] = True
    metadata["test_planner_schema_filtered_count"] = len(filtered_out)
    if filtered_out:
        metadata["test_planner_schema_filtered"] = filtered_out
    return state


# Evita que pytest lo recoja como test por nombre.
test_planner_node.__test__ = False


def _validate_hypotheses_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    """Compat alias: mantener API histórica durante la migración de nodos."""
    return validate_hypotheses_output(output, input_payload)
