"""Nodos stub del grafo RF14 (tarea RF14-02)."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from ..agents import alpha_loop, alpha_loop_result_to_dict
from ..agents.kb_index import build_kb_index
from ..agents.kb_search import KBSearchTool
from ..agents.policy_enforcer import PolicyEnforcer, ToolPolicyDeniedError
from ..catalog import aggregate_findings_by_entity, load_test_specs_from_catalog
from ..catalog.scoring import load_weights_config, resolve_ranking_top_k
from ..catalog.test_runner import TestRunner
from ..storage.paths import ruta_run
from ..storage.schema_summary import build_schema_summary
from .state import GraphState

GraphNode = Callable[[GraphState], GraphState]


def _set_node_status(
    *,
    state: GraphState,
    node_id: str,
    status: str,
    duration_ms: int,
    error: str = "",
) -> None:
    node_status = state.run_metadata.setdefault("node_status", {})
    node_timings = state.run_metadata.setdefault("node_timings_ms", {})
    if isinstance(node_status, dict):
        node_status[node_id] = status
    if isinstance(node_timings, dict):
        node_timings[node_id] = duration_ms
    if error:
        errors = state.run_metadata.setdefault("errors", [])
        if isinstance(errors, list):
            errors.append({"node_id": node_id, "error": error})


def _run_node(node_id: str, fn: GraphNode, state: GraphState) -> GraphState:
    started = perf_counter()
    try:
        out = fn(state)
    except Exception as exc:
        _set_node_status(
            state=state,
            node_id=node_id,
            status="ERROR",
            duration_ms=int((perf_counter() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    _set_node_status(
        state=out,
        node_id=node_id,
        status="OK",
        duration_ms=int((perf_counter() - started) * 1000),
    )
    return out


def _build_graph_policy_enforcer(state: GraphState) -> PolicyEnforcer:
    run_id = str(state.run_id).strip() or "unknown_run"
    tool_log_path = str(
        state.run_metadata.get("graph_tool_log_path", f"run_results/{run_id}/graph_tool_calls.jsonl")
    ).strip()
    return PolicyEnforcer.from_yaml(
        policy_path="config/agent_policies.yaml",
        tools_registry_path="config/tools_registry.yaml",
        tool_call_log_path=tool_log_path,
    )


def _tool_test_catalog(*, catalog_path: str) -> dict[str, Any]:
    specs = load_test_specs_from_catalog(catalog_path=catalog_path, validate_schema=True)
    tests: list[dict[str, Any]] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        test_id = str(spec.get("id", "")).strip()
        if not test_id:
            continue
        tests.append(
            {
                "id": test_id,
                "fraud_type": str(spec.get("fraud_type", "")).strip(),
                "name": str(spec.get("name", "")).strip(),
                "tags": [str(tag).strip() for tag in spec.get("tags", []) if str(tag).strip()]
                if isinstance(spec.get("tags"), list)
                else [],
            }
        )
    tests = sorted(tests, key=lambda row: str(row.get("id", "")))
    return {"tests": tests, "count": len(tests)}


def _tool_schema(state: GraphState) -> dict[str, Any]:
    payload = state.schema if isinstance(state.schema, dict) else {}
    tables = payload.get("tables", []) if isinstance(payload.get("tables"), list) else []
    table_names = sorted(
        str(row.get("table_name", "")).strip()
        for row in tables
        if isinstance(row, dict) and str(row.get("table_name", "")).strip()
    )
    return {"source": "schema_summary", "payload": {"table_names": table_names, "count": len(table_names)}}


def _tool_runstore_write_stub(*, run_id: str, hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    # Stub no destructivo para RF14-05; persistencia real vendrá en RF14-10.
    return {
        "operation": "write",
        "status": "OK",
        "path": f"run_results/{run_id}/hypotheses.json",
        "count": len(hypotheses),
    }


def _alphacodium_enabled(state: GraphState) -> bool:
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    return bool(metadata.get("alphacodium_enabled", True))


def _run_alpha_loop_for_node(
    *,
    state: GraphState,
    node_id: str,
    prompt_text: str,
    input_payload: dict[str, Any],
    generate_fn: Callable[[str, dict[str, Any], list[str], int], Any],
    validators: dict[str, Callable[[Any, dict[str, Any]], Any]],
    max_iter: int = 3,
) -> Any:
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    alpha_meta = metadata.setdefault("alphacodium", {})
    if not isinstance(alpha_meta, dict):
        alpha_meta = {}
        metadata["alphacodium"] = alpha_meta

    if not _alphacodium_enabled(state) or alpha_loop is None or alpha_loop_result_to_dict is None:
        output = generate_fn(prompt_text, dict(input_payload), [], 1)
        alpha_meta[node_id] = {
            "status": "BYPASSED",
            "iterations": 1,
            "artifacts_dir": "",
        }
        return output

    loop_result = alpha_loop(
        run_id=str(state.run_id),
        node_id=node_id,
        prompt_text=prompt_text,
        input_payload=input_payload,
        generate_fn=generate_fn,
        validators=validators,
        max_iter=max_iter,
    )
    alpha_meta[node_id] = alpha_loop_result_to_dict(loop_result)
    if str(loop_result.status).upper() != "OK":
        raise RuntimeError(f"alpha_loop {node_id} terminó en estado={loop_result.status}")
    return loop_result.final_output


def _validate_hypotheses_output(output: Any, _input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["hypotheses debe ser lista no vacía"]}
    errors: list[str] = []
    for idx, item in enumerate(output):
        if not isinstance(item, dict):
            errors.append(f"hypotheses[{idx}] debe ser objeto")
            continue
        hypothesis_id = str(item.get("hypothesis_id", "")).strip()
        title = str(item.get("title", "")).strip()
        if not hypothesis_id:
            errors.append(f"hypotheses[{idx}].hypothesis_id vacío")
        if not title:
            errors.append(f"hypotheses[{idx}].title vacío")
    return {"passed": len(errors) == 0, "errors": errors}


def _validate_selected_tests_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list):
        return {"passed": False, "errors": ["selected_tests debe ser lista"]}
    allowlist = input_payload.get("allowlist_ids", [])
    allowlist_set = set(str(item).strip() for item in allowlist if str(item).strip())
    errors: list[str] = []
    for idx, row in enumerate(output):
        if not isinstance(row, dict):
            errors.append(f"selected_tests[{idx}] debe ser objeto")
            continue
        hypothesis_id = str(row.get("hypothesis_id", "")).strip()
        test_id = str(row.get("test_id", "")).strip()
        if not hypothesis_id:
            errors.append(f"selected_tests[{idx}].hypothesis_id vacío")
        if not test_id:
            errors.append(f"selected_tests[{idx}].test_id vacío")
        elif allowlist_set and test_id not in allowlist_set:
            errors.append(f"selected_tests[{idx}].test_id fuera de allowlist: {test_id}")
    return {"passed": len(errors) == 0, "errors": errors}


def _validate_explanations_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["explanations debe ser lista no vacía"]}
    findings = input_payload.get("findings", [])
    try:
        _validate_explanations_guardrails(
            explanations=[item for item in output if isinstance(item, dict)],
            findings=[item for item in findings if isinstance(item, dict)],
        )
    except Exception as exc:
        return {"passed": False, "errors": [str(exc)]}
    return {"passed": True, "errors": []}


def _validate_scores_output(output: Any, _input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["scores debe ser lista no vacía"]}
    first = output[0]
    if not isinstance(first, dict):
        return {"passed": False, "errors": ["scores[0] debe ser objeto"]}
    ranking = first.get("ranking", [])
    if not isinstance(ranking, list):
        return {"passed": False, "errors": ["scores[0].ranking debe ser lista"]}
    for idx, row in enumerate(ranking):
        if not isinstance(row, dict):
            return {"passed": False, "errors": [f"ranking[{idx}] debe ser objeto"]}
        if not str(row.get("entity_key", "")).strip():
            return {"passed": False, "errors": [f"ranking[{idx}].entity_key vacío"]}
    return {"passed": True, "errors": []}


def hypothesis_planner_node(state: GraphState) -> GraphState:
    """Stub con tools RF15b + KBSearch opcional (RF14-05)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    agent_id = str(metadata.get("graph_agent_id", "expert_recommender")).strip() or "expert_recommender"
    node_id = "hypothesis_planner"
    catalog_path = str(metadata.get("catalog_path", "tests/catalog")).strip() or "tests/catalog"
    kb_search_enabled = bool(metadata.get("kb_search_enabled", False))

    enforcer = _build_graph_policy_enforcer(state)
    catalog_out = enforcer.enforce_and_call(
        agent_id=agent_id,
        tool_id="TestCatalog",
        tool_callable=_tool_test_catalog,
        node_id=node_id,
        catalog_path=catalog_path,
    )
    schema_out = enforcer.enforce_and_call(
        agent_id=agent_id,
        tool_id="Schema",
        tool_callable=lambda: _tool_schema(state),
        node_id=node_id,
    )

    kb_hits_count = 0
    kb_status = "SKIPPED"
    if kb_search_enabled:
        query = str(metadata.get("hypothesis_query", "split payments authorization threshold")).strip()
        try:
            tool = KBSearchTool(
                kb_chroma_config_path=str(metadata.get("kb_chroma_config", "config/kb_chroma.yaml")),
                base_dir=str(metadata.get("base_dir", ".")),
            )
            kb_out = tool.search(query=query, top_k=3)
            kb_hits_count = int(kb_out.get("count", 0) or 0)
            kb_status = "OK"
        except Exception as exc:
            kb_status = f"ERROR:{type(exc).__name__}"

    if not state.hypotheses:
        default_hypotheses = [
            {
                "hypothesis_id": "HYP-001",
                "title": "Split payments near approval thresholds",
                "source": "stub",
                "tool_context": {
                    "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                    "schema_tables_count": int(schema_out.get("payload", {}).get("count", 0) or 0),
                    "kb_search_status": kb_status,
                    "kb_hits_count": kb_hits_count,
                },
            }
        ]
        state.hypotheses = _run_alpha_loop_for_node(
            state=state,
            node_id="hypothesis_planner",
            prompt_text="Genera hipótesis iniciales P2P usando catálogo, schema y KB opcional.",
            input_payload={
                "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                "schema_tables_count": int(schema_out.get("payload", {}).get("count", 0) or 0),
                "kb_search_status": kb_status,
                "kb_hits_count": kb_hits_count,
            },
            generate_fn=lambda _p, _i, _f, _it: list(default_hypotheses),
            validators={"hypothesis_schema": _validate_hypotheses_output},
            max_iter=2,
        )

    try:
        runstore_out = enforcer.enforce_and_call(
            agent_id=agent_id,
            tool_id="RunStore",
            tool_callable=_tool_runstore_write_stub,
            node_id=node_id,
            run_id=str(state.run_id),
            hypotheses=state.hypotheses,
        )
        metadata["hypothesis_runstore_status"] = str(runstore_out.get("status", "UNKNOWN"))
    except ToolPolicyDeniedError:
        metadata["hypothesis_runstore_status"] = "DENIED"

    return state


def ingest_node(state: GraphState) -> GraphState:
    """Nodo de ingesta no-LLM: carga `schema_summary` en el estado (RF14-03)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    schema_summary_path = str(metadata.get("schema_summary_path", "")).strip()
    db_path = str(metadata.get("db_path", "erp.duckdb")).strip()
    schema_name = str(metadata.get("schema_name", "main")).strip() or "main"

    if schema_summary_path:
        path = Path(schema_summary_path)
        if not path.exists():
            raise FileNotFoundError(f"schema_summary_path no existe: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"schema_summary inválido en {path}")
        state.schema = payload
        metadata["ingest_source"] = "schema_summary_json"
        metadata["ingest_schema_summary_path"] = str(path)
        metadata["ingest_table_count"] = int(payload.get("table_count", 0) or 0)
        return state

    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"No existe db_path ({db_path}) ni schema_summary_path para ingest_node"
        )

    summary = build_schema_summary(db_path=db_path, schema_name=schema_name)
    state.schema = summary
    metadata["ingest_source"] = "duckdb"
    metadata["ingest_db_path"] = db_path
    metadata["ingest_schema_name"] = schema_name
    metadata["ingest_table_count"] = int(summary.get("table_count", 0) or 0)
    return state


def _score_test_against_hypothesis(
    *,
    hypothesis_text: str,
    test_spec: dict[str, Any],
) -> tuple[int, list[str]]:
    text = hypothesis_text.lower()
    test_id = str(test_spec.get("id", "")).strip()
    fraud_type = str(test_spec.get("fraud_type", "")).strip().lower()
    test_name = str(test_spec.get("name", "")).strip().lower()
    tags = [str(tag).strip().lower() for tag in test_spec.get("tags", []) if str(tag).strip()]

    score = 0
    reasons: list[str] = []

    keyword_rules: list[tuple[str, str]] = [
        ("split", "split"),
        ("threshold", "threshold"),
        ("just below", "threshold"),
        ("duplicate", "duplicate"),
        ("round", "round"),
        ("sequence", "sequence"),
        ("negative", "inventory"),
        ("material", "material"),
        ("amount", "amount"),
    ]
    for key, token in keyword_rules:
        if key in text and (
            token in test_id.lower() or token in test_name or token in ",".join(tags) or token in fraud_type
        ):
            score += 2
            reasons.append(f"keyword:{key}->{token}")

    fraud_type_aliases: list[tuple[str, str]] = [
        ("authorization", "authorization_bypass"),
        ("duplicate", "duplicate_payment"),
        ("anomaly", "amount_anomaly"),
        ("inventory", "inventory_anomaly"),
        ("pattern", "suspicious_payment_pattern"),
    ]
    for key, expected in fraud_type_aliases:
        if key in text and fraud_type == expected:
            score += 4
            reasons.append(f"fraud_type:{expected}")

    if test_id and test_id.lower() in text:
        score += 5
        reasons.append("explicit_test_id")

    return score, reasons


def test_planner_node(state: GraphState) -> GraphState:
    """Selecciona test_ids allowlist del catálogo para cada hipótesis (RF14-06)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    agent_id = str(metadata.get("graph_test_planner_agent_id", "expert_recommender")).strip()
    agent_id = agent_id or "expert_recommender"
    node_id = "test_planner"
    catalog_path = str(metadata.get("catalog_path", "tests/catalog")).strip() or "tests/catalog"
    top_n = int(metadata.get("test_planner_top_n", 2) or 2)
    if top_n <= 0:
        top_n = 1

    enforcer = _build_graph_policy_enforcer(state)
    catalog_out = enforcer.enforce_and_call(
        agent_id=agent_id,
        tool_id="TestCatalog",
        tool_callable=_tool_test_catalog,
        node_id=node_id,
        catalog_path=catalog_path,
    )
    catalog_tests = catalog_out.get("tests", []) if isinstance(catalog_out, dict) else []
    if not isinstance(catalog_tests, list):
        catalog_tests = []
    allowlist_ids = {
        str(row.get("id", "")).strip()
        for row in catalog_tests
        if isinstance(row, dict) and str(row.get("id", "")).strip()
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
        for test_spec in catalog_tests:
            if not isinstance(test_spec, dict):
                continue
            test_id = str(test_spec.get("id", "")).strip()
            if not test_id:
                continue
            if requested_allowlist and test_id not in requested_allowlist:
                continue
            score, reasons = _score_test_against_hypothesis(
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
                    "source": "planner_stub_allowlist",
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
                "source": "planner_stub_fallback",
                "score": 0,
                "match_reasons": ["fallback_first_catalog_test"],
            }
        )

    state.selected_tests = _run_alpha_loop_for_node(
        state=state,
        node_id="test_planner",
        prompt_text="Selecciona tests allowlist del catálogo para cada hipótesis.",
        input_payload={
            "allowlist_ids": sorted(allowlist_ids),
            "hypotheses_count": len(state.hypotheses),
            "top_n": top_n,
        },
        generate_fn=lambda _p, _i, _f, _it: list(selected_rows),
        validators={"selected_tests_schema": _validate_selected_tests_output},
        max_iter=2,
    )
    metadata["selected_tests_count"] = len(state.selected_tests)
    return state


# Evita que pytest lo recoja como test por nombre.
test_planner_node.__test__ = False


def kb_index_node(state: GraphState) -> GraphState:
    """Nodo no-LLM: asegura índice KB (RF14-04) con rebuild incremental."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    enabled = bool(metadata.get("kb_index_enabled", True))
    if not enabled:
        state.kb_status = {
            "status": "DISABLED",
            "index_manifest_path": "",
            "chunks_indexed": 0,
            "sources_used": 0,
            "error": "",
            "incremental_rebuild": True,
        }
        metadata["kb_index_status"] = "DISABLED"
        return state

    base_dir = str(metadata.get("base_dir", ".")).strip() or "."
    kb_sources_config = str(metadata.get("kb_sources_config", "config/kb_sources.yaml")).strip()
    kb_chunking_config = str(metadata.get("kb_chunking_config", "config/kb_chunking.yaml")).strip()
    kb_chroma_config = str(metadata.get("kb_chroma_config", "config/kb_chroma.yaml")).strip()
    kb_manifest_path = str(metadata.get("kb_manifest_path", "kb/index_manifest.json")).strip()
    kb_index_state_path = str(metadata.get("kb_index_state_path", "kb/index_state.json")).strip()

    try:
        manifest = build_kb_index(
            kb_sources_config_path=kb_sources_config,
            kb_chunking_config_path=kb_chunking_config,
            kb_chroma_config_path=kb_chroma_config,
            base_dir=base_dir,
            output_manifest_path=kb_manifest_path,
            index_state_path=kb_index_state_path,
            incremental_rebuild=True,
        )
    except Exception as exc:
        state.kb_status = {
            "status": "ERROR",
            "index_manifest_path": kb_manifest_path,
            "chunks_indexed": 0,
            "sources_used": 0,
            "error": f"{type(exc).__name__}: {exc}",
            "incremental_rebuild": True,
        }
        metadata["kb_index_status"] = "ERROR"
        raise

    state.kb_status = {
        "status": "OK",
        "index_manifest_path": kb_manifest_path,
        "chunks_indexed": int(manifest.get("chunks_indexed", 0) or 0),
        "sources_used": len(manifest.get("sources_used", [])),
        "error": "",
        "incremental_rebuild": True,
    }
    metadata["kb_index_status"] = "OK"
    metadata["kb_index_manifest_path"] = kb_manifest_path
    metadata["kb_index_state_path"] = kb_index_state_path
    return state


def executor_node(state: GraphState) -> GraphState:
    """Nodo no-LLM: ejecuta tests seleccionados y guarda findings (RF14-07)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    db_path = str(metadata.get("db_path", "erp.duckdb")).strip() or "erp.duckdb"
    schema_name = str(metadata.get("schema_name", "main")).strip() or "main"
    table_name = str(metadata.get("table_name", "fraud_1")).strip() or "fraud_1"
    catalog_path = str(metadata.get("catalog_path", "tests/catalog")).strip() or "tests/catalog"
    timeout_ms = metadata.get("executor_timeout_ms")
    timeout_value = int(timeout_ms) if isinstance(timeout_ms, int) and timeout_ms > 0 else None

    selected_ids: list[str] = []
    seen: set[str] = set()
    for row in state.selected_tests:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id", "")).strip()
        if not test_id or test_id in seen:
            continue
        seen.add(test_id)
        selected_ids.append(test_id)

    runner = TestRunner(
        db_path=db_path,
        schema_name=schema_name,
        table_name=table_name,
    )

    if not selected_ids:
        state.findings = []
        metadata["executor_status"] = "SKIPPED_NO_SELECTED_TESTS"
        metadata["executor_tests_count"] = 0
        metadata["executor_findings_total"] = 0
        return state

    run_id = str(state.run_id).strip() or "unknown_run"
    log_path = str(
        metadata.get(
            "executor_test_runner_log_path",
            f"run_results/{run_id}/graph_executor_test_runner_logs.jsonl",
        )
    ).strip()
    results = runner.run_all(
        selected_tests=selected_ids,
        catalog_path=catalog_path,
        validate_schema=True,
        timeout_ms=timeout_value,
        run_id=run_id,
        log_path=Path(log_path),
    )

    state.findings = [dict(row) for row in results if isinstance(row, dict)]
    metadata["executor_status"] = "OK"
    metadata["executor_tests_count"] = len(state.findings)
    metadata["executor_findings_total"] = sum(
        int(row.get("finding_count", 0) or 0) for row in state.findings if isinstance(row, dict)
    )
    metadata["executor_test_runner_log_path"] = log_path
    return state


def _normalize_columns(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        col = str(item).strip()
        if not col:
            continue
        if col in seen:
            continue
        seen.add(col)
        out.append(col)
    return out


def _build_explanation_from_finding(result: dict[str, Any]) -> dict[str, Any]:
    test_id = str(result.get("test_id", "")).strip()
    finding_count = int(result.get("finding_count", 0) or 0)
    status = str(result.get("status", "UNKNOWN")).strip().upper()
    fraud_type = str(result.get("fraud_type", "")).strip()
    columns = _normalize_columns(result.get("columns", []))
    rows = result.get("rows", [])
    first_entity_key = ""
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        first_entity_key = str(rows[0].get("entity_key", "")).strip()

    if status in {"ERROR", "TIMEOUT"}:
        summary = f"{test_id} terminó en {status}; revisar error_summary y logs del runner."
    elif finding_count <= 0:
        summary = f"{test_id} no activó hallazgos en este run."
    else:
        summary = (
            f"{test_id} activó {finding_count} hallazgos para fraud_type={fraud_type or 'unknown'} "
            f"usando evidencia en columnas del resultado."
        )

    return {
        "test_id": test_id,
        "status": status,
        "fraud_type": fraud_type,
        "finding_count": finding_count,
        "referenced_columns": columns[:8],
        "sample_entity_key": first_entity_key,
        "summary": summary,
        "source": "explainer_stub_guarded",
    }


def _validate_explanations_guardrails(
    *,
    explanations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
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
        if test_id not in findings_by_test:
            raise ValueError(f"Guardrail: explicación referencia test_id no ejecutado: {test_id}")

        allowed_columns = set(_normalize_columns(findings_by_test[test_id].get("columns", [])))
        referenced = _normalize_columns(item.get("referenced_columns", []))
        unknown = [col for col in referenced if col not in allowed_columns]
        if unknown:
            raise ValueError(
                f"Guardrail: explicación {test_id} referencia columnas no presentes en resultado: {unknown}"
            )


def explainer_node(state: GraphState) -> GraphState:
    """Nodo explicador con guardrails (RF14-08)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    findings = [row for row in state.findings if isinstance(row, dict)]

    if not findings:
        state.explanations = [
            {
                "test_id": "",
                "status": "NO_DATA",
                "fraud_type": "",
                "finding_count": 0,
                "referenced_columns": [],
                "sample_entity_key": "",
                "summary": "No hay resultados de ejecución para explicar.",
                "source": "explainer_stub_guarded",
            }
        ]
        metadata["explainer_status"] = "NO_FINDINGS"
        metadata["explainer_explanations_count"] = 1
        return state

    explanations = [_build_explanation_from_finding(row) for row in findings]
    state.explanations = _run_alpha_loop_for_node(
        state=state,
        node_id="expert_explainer",
        prompt_text="Genera explicación auditora con evidencia real sin alucinaciones.",
        input_payload={"findings": findings},
        generate_fn=lambda _p, _i, _f, _it: list(explanations),
        validators={"explanations_guardrails": _validate_explanations_output},
        max_iter=2,
    )
    metadata["explainer_status"] = "OK"
    metadata["explainer_explanations_count"] = len(state.explanations)
    metadata["explainer_guardrails"] = [
        "test_id debe existir en findings ejecutados",
        "referenced_columns debe ser subconjunto de result.columns",
    ]
    return state


def expert_explainer_node(state: GraphState) -> GraphState:
    """Alias semántico AG03-09 para el nodo LLM explicador."""
    return explainer_node(state)


def scoring_node(state: GraphState) -> GraphState:
    """Scoring por entidad/transacción + tipología de fraude (RF14-09)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    findings = [row for row in state.findings if isinstance(row, dict)]
    weights_config_path = str(metadata.get("weights_config", "config/weights.yaml")).strip()
    top_k_override = metadata.get("scoring_top_k")

    if not findings:
        state.scores = [
            {
                "ranking": [],
                "fraud_type_distribution": {},
                "summary": {
                    "entities_scored": 0,
                    "findings_total": 0,
                    "top_k": int(top_k_override) if isinstance(top_k_override, int) and top_k_override > 0 else 0,
                },
                "method": "weighted_entity_ranking",
                "source": "scoring_node",
            }
        ]
        metadata["scoring_status"] = "NO_FINDINGS"
        metadata["scoring_entities"] = 0
        return state

    weights_cfg = load_weights_config(weights_config_path)
    if isinstance(top_k_override, int) and top_k_override > 0:
        top_k = int(top_k_override)
    else:
        top_k = resolve_ranking_top_k(weights_config=weights_cfg, default_top_k=20)

    ranking_rows = aggregate_findings_by_entity(
        test_results=findings,
        weights_config=weights_cfg,
    )
    top_rows = ranking_rows[:top_k]

    fraud_type_distribution: dict[str, int] = {}
    for row in top_rows:
        if not isinstance(row, dict):
            continue
        fraud_types = row.get("fraud_types", [])
        if not isinstance(fraud_types, list):
            continue
        for fraud_type in fraud_types:
            key = str(fraud_type).strip()
            if not key:
                continue
            fraud_type_distribution[key] = fraud_type_distribution.get(key, 0) + 1

    scores_payload = [
        {
            "ranking": top_rows,
            "fraud_type_distribution": dict(sorted(fraud_type_distribution.items(), key=lambda item: item[0])),
            "summary": {
                "entities_scored": len(ranking_rows),
                "entities_returned": len(top_rows),
                "findings_total": sum(int(row.get("finding_count", 0) or 0) for row in findings),
                "top_k": top_k,
                "weights_config": weights_config_path,
            },
            "method": "weighted_entity_ranking",
            "source": "scoring_node",
        }
    ]
    state.scores = _run_alpha_loop_for_node(
        state=state,
        node_id="scoring",
        prompt_text="Calcula ranking por entidad y distribución por tipología de fraude.",
        input_payload={"findings_count": len(findings), "top_k": top_k},
        generate_fn=lambda _p, _i, _f, _it: list(scores_payload),
        validators={"scores_schema": _validate_scores_output},
        max_iter=2,
    )
    metadata["scoring_status"] = "OK"
    metadata["scoring_entities"] = len(ranking_rows)
    metadata["scoring_top_k"] = top_k
    return state


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _collect_alphacodium_artifacts(run_dir: Path) -> dict[str, Any]:
    alpha_dir = run_dir / "alphacodium"
    if not alpha_dir.exists():
        return {
            "base_dir": str(alpha_dir),
            "exists": False,
            "nodes": {},
            "files_total": 0,
        }

    nodes_payload: dict[str, Any] = {}
    files_total = 0
    for node_dir in sorted(alpha_dir.iterdir(), key=lambda p: p.name):
        if not node_dir.is_dir():
            continue
        manifest_path = node_dir / "iterations_manifest.jsonl"
        iteration_dirs = sorted(
            [path for path in node_dir.iterdir() if path.is_dir() and path.name.startswith("iteration_")],
            key=lambda p: p.name,
        )
        iterations_payload: list[dict[str, Any]] = []
        for iteration_dir in iteration_dirs:
            expected_files = {
                "prompt": iteration_dir / "prompt.md",
                "output": iteration_dir / "output.json",
                "validation": iteration_dir / "validation.json",
                "fix": iteration_dir / "fix.diff",
            }
            row = {
                "iteration_dir": str(iteration_dir),
                "prompt_path": str(expected_files["prompt"]) if expected_files["prompt"].exists() else "",
                "output_path": str(expected_files["output"]) if expected_files["output"].exists() else "",
                "validation_path": str(expected_files["validation"])
                if expected_files["validation"].exists()
                else "",
                "fix_path": str(expected_files["fix"]) if expected_files["fix"].exists() else "",
            }
            files_total += sum(1 for path in expected_files.values() if path.exists())
            iterations_payload.append(row)

        if manifest_path.exists():
            files_total += 1
        nodes_payload[node_dir.name] = {
            "manifest_path": str(manifest_path) if manifest_path.exists() else "",
            "iterations": iterations_payload,
            "iterations_count": len(iterations_payload),
        }

    return {
        "base_dir": str(alpha_dir),
        "exists": True,
        "nodes": nodes_payload,
        "files_total": files_total,
    }


def persist_node(state: GraphState) -> GraphState:
    """Nodo de persistencia de artefactos de grafo (RF14-10)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    run_id = str(state.run_id).strip()
    if not run_id:
        raise ValueError("run_id vacío en persist_node")

    persist_base_dir = str(metadata.get("persist_base_dir", "")).strip()
    if persist_base_dir:
        run_dir = Path(persist_base_dir) / run_id
    else:
        run_dir = ruta_run(run_id)

    graph_dir = run_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "hypotheses_json": graph_dir / "hypotheses.json",
        "selected_tests_json": graph_dir / "selected_tests.json",
        "findings_json": graph_dir / "findings.json",
        "explanations_json": graph_dir / "explanations.json",
        "scores_json": graph_dir / "scores.json",
        "graph_state_json": graph_dir / "graph_state.json",
        "manifest_json": graph_dir / "manifest.json",
    }

    _write_json(paths["hypotheses_json"], state.hypotheses)
    _write_json(paths["selected_tests_json"], state.selected_tests)
    _write_json(paths["findings_json"], state.findings)
    _write_json(paths["explanations_json"], state.explanations)
    _write_json(paths["scores_json"], state.scores)

    state_payload = {
        "run_id": state.run_id,
        "schema": state.schema,
        "kb_status": state.kb_status,
        "hypotheses_count": len(state.hypotheses),
        "selected_tests_count": len(state.selected_tests),
        "findings_count": len(state.findings),
        "explanations_count": len(state.explanations),
        "scores_count": len(state.scores),
        "run_metadata": metadata,
    }
    _write_json(paths["graph_state_json"], state_payload)

    manifest = {
        "version": "1.0.0",
        "run_id": run_id,
        "graph_dir": str(graph_dir),
        "artifacts": {key: str(value) for key, value in sorted(paths.items(), key=lambda item: item[0])},
        "alphacodium": _collect_alphacodium_artifacts(run_dir),
    }
    _write_json(paths["manifest_json"], manifest)

    metadata["persist_status"] = "OK"
    metadata["persist_graph_dir"] = str(graph_dir)
    metadata["persist_manifest_path"] = str(paths["manifest_json"])
    metadata["persist_artifacts"] = manifest["artifacts"]
    metadata["alphacodium_artifacts"] = manifest["alphacodium"]
    return state


def run_node_by_id(*, node_id: str, state: GraphState) -> GraphState:
    """Despacha y ejecuta un nodo por ID con trazabilidad básica."""
    node_map: dict[str, GraphNode] = {
        "ingest": ingest_node,
        "kb_index": kb_index_node,
        "hypothesis_planner": hypothesis_planner_node,
        "test_planner": test_planner_node,
        "executor": executor_node,
        "explainer": explainer_node,
        "expert_explainer": explainer_node,
        "scoring": scoring_node,
        "persist": persist_node,
    }
    if node_id not in node_map:
        raise ValueError(f"node_id no soportado: {node_id}")
    return _run_node(node_id=node_id, fn=node_map[node_id], state=state)
