"""Nodos stub del grafo RF14 (tarea RF14-02)."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import yaml

from ...agents import alpha_loop, alpha_loop_result_to_dict
from ...agents.kb_index import build_kb_index
from ...agents.kb_search import KBSearchTool
from ...agents.policy_enforcer import PolicyEnforcer, ToolPolicyDeniedError
from ...catalog import (
    SCORE_SCHEMA_REQUIRED_FIELDS,
    ScoringAgent,
    aggregate_findings_by_entity,
    load_test_specs_from_catalog,
    load_models_config,
    resolve_scoring_model,
)
from ...catalog import RESULT_SCHEMA_VERSION, get_result_schema_required_fields
from ...catalog.scoring import load_weights_config, resolve_ranking_top_k
from ...catalog.test_runner import TestRunner
from ...storage.paths import ruta_run
from ...storage.schema_summary import build_schema_summary
from ...config import (
    DEFAULT_BASE_DIR,
    DEFAULT_CATALOG_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_EXECUTOR_TIMEOUT_MS,
    DEFAULT_EXPLAINER_KB_TOP_K,
    DEFAULT_EXPLAINER_TOP_K,
    DEFAULT_HYPOTHESIS_KB_TOP_K,
    DEFAULT_HYPOTHESIS_MAX_ITEMS,
    DEFAULT_KB_CHROMA_CONFIG,
    DEFAULT_KB_CHUNKING_CONFIG,
    DEFAULT_KB_ENABLED,
    DEFAULT_KB_MANIFEST_PATH,
    DEFAULT_KB_SOURCES_CONFIG,
    DEFAULT_KB_STATE_PATH,
    DEFAULT_SCHEMA_NAME,
    DEFAULT_TABLE_NAME,
    DEFAULT_TEST_PLANNER_TOP_N,
    DEFAULT_WEIGHTS_CONFIG,
)
from ..prompt_registry import load_node_prompt
from ..state import GraphState
from ..observability import append_error_event

GraphNode = Callable[[GraphState], GraphState]
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _resolve_project_path(path_value: str | Path) -> str:
    raw = str(path_value).strip()
    if not raw:
        return ""
    path = Path(raw)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _langsmith_snapshot() -> dict[str, Any]:
    tracing_raw = str(os.getenv("LANGSMITH_TRACING", "")).strip().lower()
    tracing_v2_raw = str(os.getenv("LANGCHAIN_TRACING_V2", "")).strip().lower()
    tracing_enabled = tracing_raw in {"1", "true", "yes", "on"} or tracing_v2_raw in {
        "1",
        "true",
        "yes",
        "on",
    }
    api_key_present = bool(str(os.getenv("LANGSMITH_API_KEY", "")).strip())
    project = str(os.getenv("LANGSMITH_PROJECT", "")).strip()
    endpoint = str(os.getenv("LANGSMITH_ENDPOINT", "")).strip()
    trace_link = str(os.getenv("LANGSMITH_TRACE_LINK", "")).strip()
    return {
        "tracing_enabled": tracing_enabled,
        "api_key_present": api_key_present,
        "project": project,
        "endpoint": endpoint,
        "trace_link": trace_link,
    }


def _resolve_graph_node_model_config(
    *,
    node_id: str,
    metadata: dict[str, Any],
    default_model_used: str,
) -> dict[str, Any]:
    models_config_path = _resolve_project_path(
        str(metadata.get("models_config", "config/models.yaml")).strip() or "config/models.yaml"
    )
    payload: dict[str, Any] = {}
    try:
        path = Path(models_config_path)
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
    except Exception:
        payload = {}

    graph_nodes = payload.get("graph_nodes", {}) if isinstance(payload, dict) else {}
    node_cfg = graph_nodes.get(node_id, {}) if isinstance(graph_nodes, dict) else {}
    if not isinstance(node_cfg, dict):
        node_cfg = {}

    model_used = str(node_cfg.get("model_used", "")).strip() or default_model_used
    try:
        temperature = float(node_cfg.get("temperature", 0.0) or 0.0)
    except (TypeError, ValueError):
        temperature = 0.0
    try:
        max_tokens = int(node_cfg.get("max_tokens", 0) or 0)
    except (TypeError, ValueError):
        max_tokens = 0

    return {
        "node_id": node_id,
        "mode": str(node_cfg.get("mode", "stub")).strip() or "stub",
        "model_used": model_used,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "models_config_path": models_config_path,
        "source": "config" if node_cfg else "fallback",
    }


def _record_graph_node_model_config(
    *,
    node_id: str,
    metadata: dict[str, Any],
    default_model_used: str,
    overrides: dict[str, Any] | None = None,
) -> None:
    agent_model_config = metadata.setdefault("agent_model_config", {})
    if not isinstance(agent_model_config, dict):
        agent_model_config = {}
        metadata["agent_model_config"] = agent_model_config

    config = _resolve_graph_node_model_config(
        node_id=node_id,
        metadata=metadata,
        default_model_used=default_model_used,
    )
    if isinstance(overrides, dict):
        config.update(overrides)
    agent_model_config[node_id] = config


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
        append_error_event(
            run_metadata=state.run_metadata,
            node_id=node_id,
            status=status,
            error=error,
            phase="graph_node",
        )


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
        policy_path=_resolve_project_path("config/agent_policies.yaml"),
        tools_registry_path=_resolve_project_path("config/tools_registry.yaml"),
        tool_call_log_path=_resolve_project_path(tool_log_path),
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
        table_requirements: list[dict[str, Any]] = []
        data_requirements = spec.get("data_requirements", {})
        if isinstance(data_requirements, dict):
            tables = data_requirements.get("tables", [])
            if isinstance(tables, list):
                for table_req in tables:
                    if not isinstance(table_req, dict):
                        continue
                    table_name = str(table_req.get("table", "")).strip()
                    required_columns = table_req.get("required_columns", [])
                    if not isinstance(required_columns, list):
                        required_columns = []
                    cols = [str(col).strip() for col in required_columns if str(col).strip()]
                    if table_name and cols:
                        table_requirements.append(
                            {
                                "table": table_name,
                                "required_columns": cols,
                            }
                        )
        tests.append(
            {
                "id": test_id,
                "fraud_type": str(spec.get("fraud_type", "")).strip(),
                "process_step": str(spec.get("process_step", "")).strip(),
                "name": str(spec.get("name", "")).strip(),
                "table_requirements": table_requirements,
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
    columns_by_table: dict[str, list[str]] = {}
    for row in tables:
        if not isinstance(row, dict):
            continue
        table_name = str(row.get("table_name", "")).strip()
        if not table_name:
            continue
        columns = row.get("columns", [])
        if not isinstance(columns, list):
            continue
        names = []
        for col in columns:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name", col.get("column_name", ""))).strip()
            if name:
                names.append(name)
        columns_by_table[table_name] = sorted(set(names))
    return {
        "source": "schema_summary",
        "payload": {
            "table_names": table_names,
            "count": len(table_names),
            "columns_by_table": columns_by_table,
        },
    }


def _tool_data_catalog(*, data_dictionary_path: str) -> dict[str, Any]:
    path = Path(data_dictionary_path)
    if not path.exists():
        return {
            "source": "data_dictionary",
            "payload": {
                "entries": [],
                "count": 0,
                "status": "MISSING",
                "path": str(path),
            },
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "source": "data_dictionary",
            "payload": {
                "entries": [],
                "count": 0,
                "status": f"ERROR:{type(exc).__name__}",
                "path": str(path),
            },
        }

    entries = []
    if isinstance(raw, dict):
        maybe_entries = raw.get("entries", [])
        if isinstance(maybe_entries, list):
            entries = [row for row in maybe_entries if isinstance(row, dict)]

    slim_entries: list[dict[str, Any]] = []
    for row in entries:
        table = str(row.get("table", "")).strip()
        column = str(row.get("column", "")).strip()
        if not table or not column:
            continue
        slim_entries.append({"table": table, "column": column, "type": str(row.get("type", "")).strip()})

    return {
        "source": "data_dictionary",
        "payload": {
            "entries": slim_entries,
            "count": len(slim_entries),
            "status": "OK",
            "path": str(path),
        },
    }


def _build_hypotheses_from_tools(
    *,
    catalog_out: dict[str, Any],
    schema_out: dict[str, Any],
    data_catalog_out: dict[str, Any],
    kb_status: str,
    kb_query: str,
    kb_top_k: int,
    kb_hits: list[dict[str, Any]],
    max_hypotheses: int,
) -> list[dict[str, Any]]:
    catalog_tests = catalog_out.get("tests", []) if isinstance(catalog_out, dict) else []
    if not isinstance(catalog_tests, list):
        catalog_tests = []

    tests_by_fraud_type: dict[str, list[str]] = {}
    tests_by_process_step: dict[str, list[str]] = {}
    for row in catalog_tests:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("id", "")).strip()
        if not test_id:
            continue
        fraud_type = str(row.get("fraud_type", "")).strip() or "unknown"
        process_step = str(row.get("process_step", "")).strip() or "unknown_step"
        tests_by_fraud_type.setdefault(fraud_type, []).append(test_id)
        tests_by_process_step.setdefault(process_step, []).append(test_id)

    table_names = []
    schema_payload = schema_out.get("payload", {}) if isinstance(schema_out, dict) else {}
    schema_columns_by_table: dict[str, list[str]] = {}
    if isinstance(schema_payload, dict):
        names = schema_payload.get("table_names", [])
        if isinstance(names, list):
            table_names = [str(item).strip() for item in names if str(item).strip()]
        raw_cols = schema_payload.get("columns_by_table", {})
        if isinstance(raw_cols, dict):
            schema_columns_by_table = {
                str(table).strip(): [str(col).strip() for col in cols if str(col).strip()]
                for table, cols in raw_cols.items()
                if str(table).strip() and isinstance(cols, list)
            }

    data_payload = data_catalog_out.get("payload", {}) if isinstance(data_catalog_out, dict) else {}
    data_entries = data_payload.get("entries", []) if isinstance(data_payload, dict) else []
    if not isinstance(data_entries, list):
        data_entries = []
    data_evidence_raw = [
        {
            "table": str(row.get("table", "")).strip(),
            "column": str(row.get("column", "")).strip(),
        }
        for row in data_entries[:6]
        if isinstance(row, dict)
    ]
    data_evidence_raw = [row for row in data_evidence_raw if row["table"] and row["column"]]
    data_evidence = [
        row
        for row in data_evidence_raw
        if row["table"] in schema_columns_by_table and row["column"] in set(schema_columns_by_table[row["table"]])
    ]
    if not data_evidence:
        for table_name in table_names[:2]:
            for col_name in schema_columns_by_table.get(table_name, [])[:3]:
                data_evidence.append({"table": table_name, "column": col_name})

    kb_chunks = [
        str(hit.get("chunk_id", "")).strip()
        for hit in kb_hits
        if isinstance(hit, dict) and str(hit.get("chunk_id", "")).strip()
    ]

    if not tests_by_fraud_type:
        return [
            {
                "hypothesis_id": "HYP-001",
                "title": "Insufficient catalog context to derive fraud hypothesis",
                "description": "No hay tests disponibles en el catálogo para crear hipótesis específicas.",
                "fraud_type": "unknown",
                "process_step": "unknown_step",
                "evidence_requirements": [],
                "candidate_test_ids": [],
                "sources": [
                    {
                        "type": "test_catalog",
                        "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                    },
                    {
                        "type": "schema_summary",
                        "table_names": table_names,
                    },
                    {
                        "type": "data_catalog",
                        "field_count": int(data_payload.get("count", 0) or 0),
                    },
                ],
                "source": "alpha_loop_context",
                "tool_context": {
                    "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                    "schema_tables_count": int(schema_payload.get("count", 0) or 0),
                    "kb_search_status": kb_status,
                    "kb_hits_count": len(kb_chunks),
                    "data_catalog_fields_count": int(data_payload.get("count", 0) or 0),
                },
            }
        ]

    hypotheses: list[dict[str, Any]] = []
    for idx, fraud_type in enumerate(sorted(tests_by_fraud_type.keys())[:max_hypotheses], start=1):
        candidate_ids = sorted(tests_by_fraud_type[fraud_type])[:3]
        process_step = "unknown_step"
        for step, step_test_ids in tests_by_process_step.items():
            overlap = sorted(set(step_test_ids).intersection(set(candidate_ids)))
            if overlap:
                process_step = step
                break
        title = f"Hypothesis for {fraud_type.replace('_', ' ').title()} patterns"
        description = (
            f"Comprobar señales asociadas a '{fraud_type}' usando tests del catálogo y contexto de datos disponible."
        )
        sources = [
            {
                "type": "test_catalog",
                "fraud_type": fraud_type,
                "test_ids": candidate_ids,
                "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
            },
            {
                "type": "schema_summary",
                "table_names": table_names,
                "table_count": int(schema_payload.get("count", 0) or 0),
            },
            {
                "type": "data_catalog",
                "fields": data_evidence,
                "field_count": int(data_payload.get("count", 0) or 0),
            },
        ]
        if kb_status == "OK":
            sources.append(
                {
                    "type": "kb_search",
                    "query": kb_query,
                    "top_k": int(kb_top_k),
                    "chunk_ids": kb_chunks[:kb_top_k],
                    "hits_count": len(kb_chunks),
                }
            )

        evidence_requirements = [
            {"table": row["table"], "column": row["column"]}
            for row in data_evidence[:3]
            if row.get("table") and row.get("column")
        ]

        hypotheses.append(
            {
                "hypothesis_id": f"HYP-{idx:03d}",
                "title": title,
                "description": description,
                "fraud_type": fraud_type,
                "process_step": process_step,
                "evidence_requirements": evidence_requirements,
                "candidate_test_ids": candidate_ids,
                "sources": sources,
                "source": "alpha_loop_context",
                "tool_context": {
                    "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                    "schema_tables_count": int(schema_payload.get("count", 0) or 0),
                    "kb_search_status": kb_status,
                    "kb_hits_count": len(kb_chunks),
                    "data_catalog_fields_count": int(data_payload.get("count", 0) or 0),
                },
            }
        )
    return hypotheses


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


def _validate_hypotheses_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["hypotheses debe ser lista no vacía"]}
    allowed_fraud_types = {
        str(value).strip()
        for value in input_payload.get("allowed_fraud_types", [])
        if str(value).strip()
    }
    allowed_process_steps = {
        str(value).strip()
        for value in input_payload.get("allowed_process_steps", [])
        if str(value).strip()
    }
    schema_columns_by_table_raw = input_payload.get("schema_columns_by_table", {})
    schema_columns_by_table: dict[str, set[str]] = {}
    if isinstance(schema_columns_by_table_raw, dict):
        for table, columns in schema_columns_by_table_raw.items():
            table_name = str(table).strip()
            if not table_name:
                continue
            if isinstance(columns, list):
                schema_columns_by_table[table_name] = {
                    str(col).strip() for col in columns if str(col).strip()
                }

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
        fraud_type = str(item.get("fraud_type", "")).strip()
        process_step = str(item.get("process_step", "")).strip()
        if not fraud_type:
            errors.append(f"hypotheses[{idx}].fraud_type vacío")
        elif allowed_fraud_types and fraud_type not in allowed_fraud_types:
            errors.append(f"hypotheses[{idx}].fraud_type fuera de catálogo: {fraud_type}")
        if not process_step:
            errors.append(f"hypotheses[{idx}].process_step vacío")
        elif allowed_process_steps and process_step not in allowed_process_steps:
            errors.append(f"hypotheses[{idx}].process_step fuera de catálogo: {process_step}")

        evidence_requirements = item.get("evidence_requirements", [])
        if not isinstance(evidence_requirements, list):
            errors.append(f"hypotheses[{idx}].evidence_requirements debe ser lista")
            evidence_requirements = []
        for req_idx, req in enumerate(evidence_requirements):
            if not isinstance(req, dict):
                errors.append(f"hypotheses[{idx}].evidence_requirements[{req_idx}] debe ser objeto")
                continue
            table = str(req.get("table", "")).strip()
            column = str(req.get("column", "")).strip()
            if not table or not column:
                errors.append(
                    f"hypotheses[{idx}].evidence_requirements[{req_idx}] requiere table/column no vacíos"
                )
                continue
            if schema_columns_by_table:
                table_cols = schema_columns_by_table.get(table)
                if table_cols is None:
                    errors.append(f"hypotheses[{idx}] evidencia usa tabla no existente: {table}")
                    continue
                if column not in table_cols:
                    errors.append(
                        f"hypotheses[{idx}] evidencia usa columna no existente: {table}.{column}"
                    )
        sources = item.get("sources", [])
        if not isinstance(sources, list) or not sources:
            errors.append(f"hypotheses[{idx}].sources debe ser lista no vacía")
            continue
        source_types = {
            str(source.get("type", "")).strip()
            for source in sources
            if isinstance(source, dict)
        }
        if "test_catalog" not in source_types:
            errors.append(f"hypotheses[{idx}].sources sin test_catalog")
        if "schema_summary" not in source_types:
            errors.append(f"hypotheses[{idx}].sources sin schema_summary")
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
    catalog_ids_raw = input_payload.get("catalog_test_ids", [])
    schema_columns_raw = input_payload.get("schema_columns", [])
    catalog_test_ids = (
        {
            str(item).strip()
            for item in catalog_ids_raw
            if str(item).strip()
        }
        if isinstance(catalog_ids_raw, list)
        else set()
    )
    schema_columns = (
        {
            str(item).strip()
            for item in schema_columns_raw
            if str(item).strip()
        }
        if isinstance(schema_columns_raw, list)
        else set()
    )
    try:
        _validate_explanations_guardrails(
            explanations=[item for item in output if isinstance(item, dict)],
            findings=[item for item in findings if isinstance(item, dict)],
            catalog_test_ids=catalog_test_ids,
            schema_columns=schema_columns,
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
    missing_schema_fields = [field for field in SCORE_SCHEMA_REQUIRED_FIELDS if field not in first]
    if missing_schema_fields:
        return {
            "passed": False,
            "errors": [f"scores[0] no cumple ScoreSchema, faltan: {missing_schema_fields}"],
        }
    ranking = first.get("ranking", [])
    if not isinstance(ranking, list):
        return {"passed": False, "errors": ["scores[0].ranking debe ser lista"]}
    for idx, row in enumerate(ranking):
        if not isinstance(row, dict):
            return {"passed": False, "errors": [f"ranking[{idx}] debe ser objeto"]}
        if not str(row.get("entity_key", "")).strip():
            return {"passed": False, "errors": [f"ranking[{idx}].entity_key vacío"]}
    fraud_type_probs = first.get("fraud_type_probs", [])
    if fraud_type_probs:
        if not isinstance(fraud_type_probs, list):
            return {"passed": False, "errors": ["scores[0].fraud_type_probs debe ser lista"]}
        for idx, row in enumerate(fraud_type_probs):
            if not isinstance(row, dict):
                return {"passed": False, "errors": [f"fraud_type_probs[{idx}] debe ser objeto"]}
            if not str(row.get("fraud_type", "")).strip():
                return {"passed": False, "errors": [f"fraud_type_probs[{idx}].fraud_type vacío"]}
            prob = float(row.get("probability", 0.0) or 0.0)
            if prob < 0.0 or prob > 1.0:
                return {
                    "passed": False,
                    "errors": [f"fraud_type_probs[{idx}].probability fuera de [0,1]: {prob}"],
                }
    return {"passed": True, "errors": []}


def _validate_scoring_evidence_and_probability_sum(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["scores debe ser lista no vacía"]}
    first = output[0]
    if not isinstance(first, dict):
        return {"passed": False, "errors": ["scores[0] debe ser objeto"]}
    fraud_type_probs = first.get("fraud_type_probs", [])
    if not isinstance(fraud_type_probs, list):
        return {"passed": False, "errors": ["scores[0].fraud_type_probs debe ser lista"]}
    if not fraud_type_probs:
        return {"passed": True, "errors": []}

    findings = input_payload.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    hypotheses = input_payload.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        hypotheses = []
    findings_by_fraud_type: dict[str, set[str]] = {}
    all_test_ids: set[str] = set()
    allowed_fraud_types: set[str] = set()
    for row in findings:
        if not isinstance(row, dict):
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        test_id = str(row.get("test_id", "")).strip()
        if not fraud_type or not test_id:
            continue
        allowed_fraud_types.add(fraud_type)
        all_test_ids.add(test_id)
        findings_by_fraud_type.setdefault(fraud_type, set()).add(test_id)
    for row in hypotheses:
        if not isinstance(row, dict):
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        if fraud_type:
            allowed_fraud_types.add(fraud_type)

    errors: list[str] = []
    total_prob = 0.0
    for idx, row in enumerate(fraud_type_probs):
        if not isinstance(row, dict):
            errors.append(f"fraud_type_probs[{idx}] debe ser objeto")
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        prob = float(row.get("probability", 0.0) or 0.0)
        total_prob += prob
        if allowed_fraud_types and fraud_type not in allowed_fraud_types:
            errors.append(f"fraud_type_probs[{idx}].fraud_type fuera de taxonomía permitida: {fraud_type}")
        source_test_ids = row.get("source_test_ids", [])
        if not isinstance(source_test_ids, list):
            errors.append(f"fraud_type_probs[{idx}].source_test_ids debe ser lista")
            continue
        allowed_ids = findings_by_fraud_type.get(fraud_type, set())
        unknown = [
            str(test_id).strip()
            for test_id in source_test_ids
            if str(test_id).strip() and str(test_id).strip() not in allowed_ids
        ]
        if unknown:
            errors.append(
                f"fraud_type_probs[{idx}] referencia source_test_ids no presentes en findings: {unknown}"
            )

    if abs(total_prob - 1.0) > 0.001:
        errors.append(f"fraud_type_probs.probability suma {total_prob:.6f} (esperado ~1.0)")

    final_label = str(first.get("final_label", "")).strip()
    if final_label:
        known_labels = {
            str(row.get("fraud_type", "")).strip()
            for row in fraud_type_probs
            if isinstance(row, dict) and str(row.get("fraud_type", "")).strip()
        }
        if final_label not in known_labels:
            errors.append(f"final_label fuera de fraud_type_probs: {final_label}")
        if allowed_fraud_types and final_label not in allowed_fraud_types:
            errors.append(f"final_label fuera de taxonomía permitida: {final_label}")

    evidence_summary = str(first.get("evidence_summary", "")).strip()
    if all_test_ids:
        references_known_test = any(test_id in evidence_summary for test_id in sorted(all_test_ids))
        if not references_known_test:
            errors.append("evidence_summary no referencia test_id real de findings")
    return {"passed": len(errors) == 0, "errors": errors}


def hypothesis_planner_node(state: GraphState) -> GraphState:
    """Genera hipótesis con trazabilidad de fuentes (RF15c-03)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    _record_graph_node_model_config(
        node_id="hypothesis_planner",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
    )
    agent_id = str(metadata.get("graph_agent_id", "expert_recommender")).strip() or "expert_recommender"
    node_id = "hypothesis_planner"
    catalog_path = _resolve_project_path(
        str(metadata.get("catalog_path", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
    )
    data_dictionary_path = _resolve_project_path(
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
        data_catalog_out = enforcer.enforce_and_call(
            agent_id=agent_id,
            tool_id="DataCatalog",
            tool_callable=_tool_data_catalog,
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
            tool = KBSearchTool(
                kb_chroma_config_path=_resolve_project_path(
                    str(metadata.get("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)).strip()
                    or DEFAULT_KB_CHROMA_CONFIG
                ),
                base_dir=_resolve_project_path(
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
        default_hypotheses = _build_hypotheses_from_tools(
            catalog_out=catalog_out,
            schema_out=schema_out,
            data_catalog_out=data_catalog_out,
            kb_status=kb_status,
            kb_query=kb_query,
            kb_top_k=kb_top_k,
            kb_hits=kb_hits,
            max_hypotheses=max_hypotheses,
        )
        state.hypotheses = _run_alpha_loop_for_node(
            state=state,
            node_id="hypothesis_planner",
            prompt_text=str(prompt_info.get("text", "")),
            input_payload={
                "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                "schema_tables_count": int(schema_out.get("payload", {}).get("count", 0) or 0),
                "data_catalog_fields_count": int(data_catalog_out.get("payload", {}).get("count", 0) or 0),
                "kb_search_status": kb_status,
                "kb_hits_count": len(kb_hits),
                "kb_top_k": kb_top_k,
                "allowed_fraud_types": allowed_fraud_types,
                "allowed_process_steps": allowed_process_steps,
                "schema_columns_by_table": schema_columns_by_table,
            },
            generate_fn=lambda _p, _i, _f, _it: list(default_hypotheses),
            validators={"hypothesis_schema": _validate_hypotheses_output},
            max_iter=2,
        )

    if enforcer is None:
        metadata["hypothesis_runstore_status"] = "SKIPPED_NO_ENFORCER"
    else:
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
        except Exception as exc:
            metadata["hypothesis_runstore_status"] = f"ERROR: {type(exc).__name__}: {exc}"

    return state


def ingest_node(state: GraphState) -> GraphState:
    """Nodo de ingesta no-LLM: carga `schema_summary` en el estado (RF14-03)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    schema_summary_path = str(metadata.get("schema_summary_path", "")).strip()
    db_path = _resolve_project_path(str(metadata.get("db_path", DEFAULT_DB_PATH)).strip() or DEFAULT_DB_PATH)
    schema_name = str(metadata.get("schema_name", DEFAULT_SCHEMA_NAME)).strip() or DEFAULT_SCHEMA_NAME

    if schema_summary_path:
        path = Path(_resolve_project_path(schema_summary_path))
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


def _build_schema_columns_lookup(schema_payload: dict[str, Any]) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = {}
    tables = schema_payload.get("tables", []) if isinstance(schema_payload.get("tables"), list) else []
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_name = str(table.get("table_name", "")).strip()
        if not table_name:
            continue
        cols_raw = table.get("columns", [])
        if not isinstance(cols_raw, list):
            continue
        col_names = {
            str(col.get("name", col.get("column_name", ""))).strip()
            for col in cols_raw
            if isinstance(col, dict) and str(col.get("name", col.get("column_name", ""))).strip()
        }
        lookup[table_name] = col_names
    return lookup


def _test_spec_is_schema_compatible(
    *,
    test_spec: dict[str, Any],
    schema_columns_lookup: dict[str, set[str]],
) -> tuple[bool, str]:
    requirements = test_spec.get("table_requirements", [])
    if not isinstance(requirements, list) or not requirements:
        return True, ""
    test_id = str(test_spec.get("id", "")).strip() or "<unknown_test>"
    for req in requirements:
        if not isinstance(req, dict):
            continue
        table_name = str(req.get("table", "")).strip()
        required_columns = req.get("required_columns", [])
        if not table_name:
            continue
        if table_name not in schema_columns_lookup:
            return False, f"{test_id}: tabla requerida no disponible en schema_summary: {table_name}"
        if not isinstance(required_columns, list):
            continue
        missing_columns = [
            str(col).strip()
            for col in required_columns
            if str(col).strip() and str(col).strip() not in schema_columns_lookup[table_name]
        ]
        if missing_columns:
            return (
                False,
                f"{test_id}: columnas requeridas no disponibles en {table_name}: {missing_columns}",
            )
    return True, ""


def test_planner_node(state: GraphState) -> GraphState:
    """Selecciona test_ids allowlist del catálogo para cada hipótesis (RF14-06/RF15c-05)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    _record_graph_node_model_config(
        node_id="test_planner",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
    )
    agent_id = str(metadata.get("graph_test_planner_agent_id", "expert_recommender")).strip()
    agent_id = agent_id or "expert_recommender"
    node_id = "test_planner"
    catalog_path = _resolve_project_path(
        str(metadata.get("catalog_path", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
    )
    top_n = int(metadata.get("test_planner_top_n", DEFAULT_TEST_PLANNER_TOP_N) or DEFAULT_TEST_PLANNER_TOP_N)
    if top_n <= 0:
        top_n = 1

    catalog_out: dict[str, Any] = {"tests": [], "count": 0}
    try:
        enforcer = _build_graph_policy_enforcer(state)
        catalog_out = enforcer.enforce_and_call(
            agent_id=agent_id,
            tool_id="TestCatalog",
            tool_callable=_tool_test_catalog,
            node_id=node_id,
            catalog_path=catalog_path,
        )
        metadata["test_planner_tooling_status"] = "OK"
    except Exception as exc:
        metadata["test_planner_tooling_status"] = f"ERROR: {type(exc).__name__}: {exc}"
        try:
            catalog_out = _tool_test_catalog(catalog_path=catalog_path)
            metadata["test_planner_tooling_fallback"] = "DIRECT_CATALOG"
        except Exception as inner_exc:
            metadata["test_planner_tooling_fallback"] = f"ERROR: {type(inner_exc).__name__}: {inner_exc}"
            catalog_out = {"tests": [], "count": 0}
    catalog_tests = catalog_out.get("tests", []) if isinstance(catalog_out, dict) else []
    if not isinstance(catalog_tests, list):
        catalog_tests = []
    schema_lookup = _build_schema_columns_lookup(state.schema if isinstance(state.schema, dict) else {})
    compatible_catalog_tests: list[dict[str, Any]] = []
    filtered_out: list[str] = []
    if not schema_lookup:
        compatible_catalog_tests = [row for row in catalog_tests if isinstance(row, dict)]
    else:
        for test_spec in catalog_tests:
            if not isinstance(test_spec, dict):
                continue
            compatible, reason = _test_spec_is_schema_compatible(
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

    prompt_info = load_node_prompt(
        node_id="test_planner",
        fallback_text="Selecciona tests allowlist del catálogo para cada hipótesis.",
        registry_path=metadata.get("prompt_registry_path"),
    )
    metadata["test_planner_prompt_path"] = str(prompt_info.get("path", "")).strip()
    metadata["test_planner_prompt_version"] = str(prompt_info.get("version", "")).strip()
    metadata["test_planner_prompt_hash"] = str(prompt_info.get("hash", "")).strip()
    metadata["test_planner_prompt_status"] = str(prompt_info.get("status", "")).strip()

    state.selected_tests = _run_alpha_loop_for_node(
        state=state,
        node_id="test_planner",
        prompt_text=str(prompt_info.get("text", "")),
        input_payload={
            "allowlist_ids": sorted(allowlist_ids),
            "hypotheses_count": len(state.hypotheses),
            "top_n": top_n,
        },
        generate_fn=lambda _p, _i, _f, _it: list(selected_rows),
        validators={"selected_tests_schema": _validate_selected_tests_output},
        max_iter=2,
    )
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


def kb_index_node(state: GraphState) -> GraphState:
    """Nodo no-LLM: asegura índice KB (RF14-04) con rebuild incremental."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    enabled = bool(metadata.get("kb_index_enabled", DEFAULT_KB_ENABLED))
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

    base_dir = str(metadata.get("base_dir", DEFAULT_BASE_DIR)).strip() or DEFAULT_BASE_DIR
    kb_sources_config = str(metadata.get("kb_sources_config", DEFAULT_KB_SOURCES_CONFIG)).strip()
    kb_chunking_config = str(metadata.get("kb_chunking_config", DEFAULT_KB_CHUNKING_CONFIG)).strip()
    kb_chroma_config = str(metadata.get("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)).strip()
    kb_manifest_path = str(metadata.get("kb_manifest_path", DEFAULT_KB_MANIFEST_PATH)).strip()
    kb_index_state_path = str(metadata.get("kb_index_state_path", DEFAULT_KB_STATE_PATH)).strip()

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
    _record_graph_node_model_config(
        node_id="executor",
        metadata=metadata,
        default_model_used="deterministic-sql-runner",
        overrides={"mode": "deterministic"},
    )
    db_path = _resolve_project_path(
        str(metadata.get("db_path", DEFAULT_DB_PATH)).strip() or DEFAULT_DB_PATH
    )
    schema_name = str(metadata.get("schema_name", DEFAULT_SCHEMA_NAME)).strip() or DEFAULT_SCHEMA_NAME
    table_name = str(metadata.get("table_name", DEFAULT_TABLE_NAME)).strip() or DEFAULT_TABLE_NAME
    catalog_path = _resolve_project_path(
        str(metadata.get("catalog_path", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
    )
    timeout_ms = metadata.get("executor_timeout_ms")
    if timeout_ms is None:
        timeout_ms = DEFAULT_EXECUTOR_TIMEOUT_MS
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
        state.test_runs = []
        metadata["executor_status"] = "SKIPPED_NO_SELECTED_TESTS"
        metadata["executor_tests_count"] = 0
        metadata["executor_findings_total"] = 0
        return state

    run_id = str(state.run_id).strip() or "unknown_run"
    log_path = _resolve_project_path(
        metadata.get(
            "executor_test_runner_log_path",
            f"run_results/{run_id}/graph_executor_test_runner_logs.jsonl",
        )
    )
    try:
        results = runner.run_all(
            selected_tests=selected_ids,
            catalog_path=catalog_path,
            validate_schema=True,
            timeout_ms=timeout_value,
            run_id=run_id,
            log_path=Path(log_path),
        )
        metadata["executor_runner_status"] = "OK"
    except Exception as exc:
        metadata["executor_runner_status"] = f"ERROR: {type(exc).__name__}: {exc}"
        # Fallback robusto para stub CI: evita abortar el grafo por entorno/catálogo.
        fallback_test_id = selected_ids[0] if selected_ids else "TST-STUB-FALLBACK"
        results = [
            {
                "result_schema_version": RESULT_SCHEMA_VERSION,
                "generated_at_utc": "",
                "test_id": fallback_test_id,
                "test_version": "0.0.0-stub",
                "fraud_type": "unknown",
                "status": "OK",
                "finding_count": 1,
                "duration_ms": 0,
                "columns": ["entity_key", "fallback_reason"],
                "rows": [
                    {
                        "entity_key": "stub=fallback",
                        "keys": {"stub": "fallback"},
                        "evidence_columns": ["fallback_reason"],
                        "metrics": {"fallback": 1},
                        "fallback_reason": f"{type(exc).__name__}: {exc}",
                    }
                ],
                "metadata": {
                    "implementation_type": "stub_fallback",
                    "executed_on": f"{schema_name}.{table_name}",
                },
            }
        ]

    normalized_results = [_normalize_result_schema_payload(row) for row in results if isinstance(row, dict)]
    state.findings = [dict(row) for row in normalized_results]
    state.test_runs = [_to_test_run_record(row) for row in normalized_results]
    metadata["executor_status"] = "OK"
    metadata["executor_tests_count"] = len(state.findings)
    metadata["executor_findings_total"] = sum(
        int(row.get("finding_count", 0) or 0) for row in state.findings if isinstance(row, dict)
    )
    metadata["executor_result_schema_version"] = RESULT_SCHEMA_VERSION
    metadata["executor_test_runs_count"] = len(state.test_runs)
    metadata["executor_test_runner_log_path"] = log_path
    return state


def _normalize_result_schema_payload(result: dict[str, Any]) -> dict[str, Any]:
    row = dict(result)
    required_fields = get_result_schema_required_fields()
    defaults: dict[str, Any] = {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "generated_at_utc": "",
        "test_id": "",
        "test_version": "",
        "fraud_type": "",
        "status": "UNKNOWN",
        "finding_count": 0,
        "duration_ms": int(row.get("runner_duration_ms", 0) or row.get("duration_ms", 0) or 0),
        "columns": [],
        "rows": [],
        "metadata": {},
    }
    for field in required_fields:
        if field not in row or row.get(field) is None:
            row[field] = defaults.get(field)
    row["result_schema_version"] = str(row.get("result_schema_version") or RESULT_SCHEMA_VERSION)
    row["test_id"] = str(row.get("test_id", "")).strip()
    row["test_version"] = str(row.get("test_version", "")).strip()
    row["fraud_type"] = str(row.get("fraud_type", "")).strip()
    row["status"] = str(row.get("status", "UNKNOWN")).strip().upper() or "UNKNOWN"
    row["finding_count"] = int(row.get("finding_count", 0) or 0)
    row["duration_ms"] = int(row.get("duration_ms", 0) or 0)
    if not isinstance(row.get("columns"), list):
        row["columns"] = []
    if not isinstance(row.get("rows"), list):
        row["rows"] = []
    if not isinstance(row.get("metadata"), dict):
        row["metadata"] = {}
    return row


def _to_test_run_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_id": str(result.get("test_id", "")).strip(),
        "version": str(result.get("test_version", "")).strip(),
        "status": str(result.get("status", "UNKNOWN")).strip().upper(),
        "duration_ms": int(result.get("runner_duration_ms", result.get("duration_ms", 0)) or 0),
        "error_summary": str(result.get("error_summary", "")).strip(),
        "finding_count": int(result.get("finding_count", 0) or 0),
    }


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


def _build_explanation_from_finding(result: dict[str, Any], *, entity_key: str = "") -> dict[str, Any]:
    test_id = str(result.get("test_id", "")).strip()
    finding_count = int(result.get("finding_count", 0) or 0)
    status = str(result.get("status", "UNKNOWN")).strip().upper()
    fraud_type = str(result.get("fraud_type", "")).strip()
    columns = _normalize_columns(result.get("columns", []))
    rows = result.get("rows", [])
    first_entity_key = ""
    first_keys: dict[str, Any] = {}
    first_evidence_columns: list[str] = []
    selected_row: dict[str, Any] = {}
    if isinstance(rows, list):
        if entity_key:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                row_entity_key = str(row.get("entity_key", "")).strip()
                if row_entity_key == entity_key:
                    selected_row = row
                    break
        if not selected_row and rows and isinstance(rows[0], dict):
            selected_row = rows[0]

    if selected_row:
        first_entity_key = str(selected_row.get("entity_key", "")).strip()
        maybe_keys = selected_row.get("keys")
        if isinstance(maybe_keys, dict):
            first_keys = {str(k): str(v) for k, v in maybe_keys.items() if str(k).strip()}
        maybe_evidence = selected_row.get("evidence_columns")
        if isinstance(maybe_evidence, list):
            first_evidence_columns = _normalize_columns(maybe_evidence)

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
        "cited_test_id": test_id,
        "status": status,
        "fraud_type": fraud_type,
        "finding_count": finding_count,
        "referenced_columns": columns[:8],
        "cited_keys": first_keys,
        "cited_evidence_columns": first_evidence_columns,
        "sample_entity_key": first_entity_key,
        "summary": summary,
        "source": "explainer_stub_guarded",
    }


def _build_explanations_for_ranked_entities(
    *,
    findings: list[dict[str, Any]],
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    if top_k <= 0:
        return []
    top_entities: list[str] = []
    for row in ranking[:top_k]:
        if not isinstance(row, dict):
            continue
        entity_key = str(row.get("entity_key", "")).strip()
        if entity_key:
            top_entities.append(entity_key)
    if not top_entities:
        return []

    explanations: list[dict[str, Any]] = []
    for entity_key in top_entities:
        matched = False
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            rows = finding.get("rows", [])
            if not isinstance(rows, list):
                continue
            if not any(
                isinstance(row, dict) and str(row.get("entity_key", "")).strip() == entity_key
                for row in rows
            ):
                continue
            item = _build_explanation_from_finding(finding, entity_key=entity_key)
            item["summary"] = (
                f"{item['test_id']} respalda hallazgo para entity_key={entity_key} "
                f"con evidencia citada del resultado."
            )
            explanations.append(item)
            matched = True
            break
        if not matched:
            continue
    return explanations


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

        allowed_columns = set(_normalize_columns(findings_by_test[test_id].get("columns", [])))
        referenced = _normalize_columns(item.get("referenced_columns", []))
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
            allowed_evidence = _normalize_columns(maybe_evidence)
        cited_evidence = _normalize_columns(item.get("cited_evidence_columns", []))
        if cited_evidence:
            unknown_evidence = [col for col in cited_evidence if col not in set(allowed_evidence)]
            if unknown_evidence:
                raise ValueError(
                    f"Guardrail: explicación {test_id} cita evidence_columns no presentes: {unknown_evidence}"
                )


def _sanitize_explanations_against_findings(
    *,
    explanations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings_by_test: dict[str, dict[str, Any]] = {}
    for row in findings:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id", "")).strip()
        if test_id:
            findings_by_test[test_id] = row

    sanitized: list[dict[str, Any]] = []
    for item in explanations:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        test_id = str(row.get("test_id", "")).strip()
        if not test_id or test_id not in findings_by_test:
            continue

        finding = findings_by_test[test_id]
        row["cited_test_id"] = test_id
        allowed_columns = set(_normalize_columns(finding.get("columns", [])))
        row["referenced_columns"] = [
            col for col in _normalize_columns(row.get("referenced_columns", [])) if col in allowed_columns
        ]

        finding_rows = finding.get("rows", [])
        first_row = finding_rows[0] if isinstance(finding_rows, list) and finding_rows else {}
        allowed_keys = first_row.get("keys", {}) if isinstance(first_row, dict) else {}
        if not isinstance(allowed_keys, dict):
            allowed_keys = {}
        cited_keys = row.get("cited_keys", {})
        if not isinstance(cited_keys, dict):
            cited_keys = {}
        row["cited_keys"] = {
            str(k): str(v)
            for k, v in cited_keys.items()
            if str(k).strip() and str(k) in allowed_keys
        }

        allowed_evidence = []
        maybe_evidence = first_row.get("evidence_columns", []) if isinstance(first_row, dict) else []
        if isinstance(maybe_evidence, list):
            allowed_evidence = _normalize_columns(maybe_evidence)
        row["cited_evidence_columns"] = [
            col
            for col in _normalize_columns(row.get("cited_evidence_columns", []))
            if col in set(allowed_evidence)
        ]
        sanitized.append(row)
    return sanitized


def _build_structured_explainer_feedback(errors: list[str]) -> list[dict[str, Any]]:
    structured: list[dict[str, Any]] = []
    for raw in errors:
        err = str(raw).strip()
        if not err:
            continue
        code = "UNKNOWN"
        if "no ejecutado" in err or "fuera de catálogo" in err:
            code = "TEST_ID_INVALID"
        elif "columnas no presentes" in err:
            code = "REFERENCED_COLUMNS_INVALID"
        elif "keys inexistentes" in err or "fuera de schema_summary" in err:
            code = "CITED_KEYS_INVALID"
        elif "evidence_columns no presentes" in err:
            code = "EVIDENCE_COLUMNS_INVALID"
        structured.append({"code": code, "message": err})
    return structured


def _build_acfe_reference_via_kb(
    *,
    kb_enabled: bool,
    kb_query: str,
    kb_top_k: int,
    kb_chroma_config_path: str,
    base_dir: str,
) -> dict[str, Any]:
    if not kb_enabled:
        return {"status": "SKIPPED", "query": kb_query, "hits": []}
    try:
        tool = KBSearchTool(
            kb_chroma_config_path=kb_chroma_config_path,
            base_dir=base_dir,
        )
        result = tool.search(query=kb_query, top_k=kb_top_k)
        hits = result.get("hits", []) if isinstance(result, dict) else []
        out_hits = []
        for row in hits[:kb_top_k]:
            if not isinstance(row, dict):
                continue
            metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
            out_hits.append(
                {
                    "chunk_id": str(row.get("chunk_id", "")).strip(),
                    "score": float(row.get("score", 0.0) or 0.0),
                    "source_path": str(metadata.get("source_path", "")).strip(),
                    "source_id": str(metadata.get("source_id", "")).strip(),
                }
            )
        return {"status": "OK", "query": kb_query, "hits": out_hits}
    except Exception as exc:
        return {
            "status": f"ERROR:{type(exc).__name__}",
            "query": kb_query,
            "hits": [],
            "error": str(exc),
        }


def explainer_node(state: GraphState) -> GraphState:
    """Nodo explicador con guardrails (RF14-08)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    _record_graph_node_model_config(
        node_id="expert_explainer",
        metadata=metadata,
        default_model_used="gpt-5.4-mini",
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
    kb_chroma_config_path = _resolve_project_path(
        str(metadata.get("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)).strip() or DEFAULT_KB_CHROMA_CONFIG
    )
    base_dir = _resolve_project_path(str(metadata.get("base_dir", DEFAULT_BASE_DIR)).strip() or DEFAULT_BASE_DIR)
    catalog_path = _resolve_project_path(
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

    ranked_explanations = _build_explanations_for_ranked_entities(
        findings=findings,
        ranking=[row for row in state.ranking if isinstance(row, dict)],
        top_k=explainer_top_k,
    )
    seed_explanations = ranked_explanations if ranked_explanations else [
        _build_explanation_from_finding(row) for row in findings
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
        item["acfe_reference"] = _build_acfe_reference_via_kb(
            kb_enabled=kb_enabled,
            kb_query=acfe_query,
            kb_top_k=kb_top_k,
            kb_chroma_config_path=kb_chroma_config_path,
            base_dir=base_dir,
        )
        explanations.append(item)

    simulate_hallucination_once = bool(metadata.get("explainer_simulate_hallucination_once", False))

    def _generate_explanations(
        _prompt: str,
        input_payload: dict[str, Any],
        repair_feedback: list[str],
        iteration: int,
    ) -> list[dict[str, Any]]:
        base = [dict(row) for row in explanations if isinstance(row, dict)]
        if iteration == 1 and not repair_feedback and simulate_hallucination_once and base:
            base[0]["referenced_columns"] = list(_normalize_columns(base[0].get("referenced_columns", []))) + [
                "NO_EXISTE_COL"
            ]
            base[0]["cited_keys"] = {"NO_KEY": "X"}
            base[0]["cited_evidence_columns"] = list(
                _normalize_columns(base[0].get("cited_evidence_columns", []))
            ) + ["NO_EVIDENCE"]
            return base
        if repair_feedback:
            findings_payload = input_payload.get("findings", [])
            if isinstance(findings_payload, list):
                metadata["explainer_last_repair_feedback"] = _build_structured_explainer_feedback(repair_feedback)
                return _sanitize_explanations_against_findings(
                    explanations=base,
                    findings=[row for row in findings_payload if isinstance(row, dict)],
                )
        return base

    prompt_info = load_node_prompt(
        node_id="expert_explainer",
        fallback_text="Genera explicación auditora con evidencia real sin alucinaciones.",
        registry_path=metadata.get("prompt_registry_path"),
    )
    metadata["explainer_prompt_path"] = str(prompt_info.get("path", "")).strip()
    metadata["explainer_prompt_version"] = str(prompt_info.get("version", "")).strip()
    metadata["explainer_prompt_hash"] = str(prompt_info.get("hash", "")).strip()
    metadata["explainer_prompt_status"] = str(prompt_info.get("status", "")).strip()

    state.explanations = _run_alpha_loop_for_node(
        state=state,
        node_id="expert_explainer",
        prompt_text=str(prompt_info.get("text", "")),
        input_payload={
            "findings": findings,
            "catalog_test_ids": sorted(catalog_test_ids),
            "schema_columns": sorted(schema_columns),
        },
        generate_fn=_generate_explanations,
        validators={"explanations_guardrails": _validate_explanations_output},
        max_iter=2,
    )
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


def scoring_node(state: GraphState) -> GraphState:
    """Scoring por entidad/transacción + tipología de fraude (RF14-09)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    _record_graph_node_model_config(
        node_id="scoring",
        metadata=metadata,
        default_model_used="scoring-stub-v2",
    )
    findings = [row for row in state.findings if isinstance(row, dict)]
    weights_config_path = _resolve_project_path(
        str(metadata.get("weights_config", DEFAULT_WEIGHTS_CONFIG)).strip() or DEFAULT_WEIGHTS_CONFIG
    )
    models_config_path = _resolve_project_path(
        str(metadata.get("models_config", "config/models.yaml")).strip() or "config/models.yaml"
    )
    scoring_model_profile = str(metadata.get("scoring_model_profile", "")).strip()
    top_k_override = metadata.get("scoring_top_k")
    simulate_invalid_once = bool(metadata.get("scoring_simulate_invalid_once", False))
    scoring_compare_profiles_raw = metadata.get("scoring_compare_profiles", [])
    if isinstance(scoring_compare_profiles_raw, str):
        scoring_compare_profiles = [
            item.strip() for item in scoring_compare_profiles_raw.split(",") if item.strip()
        ]
    elif isinstance(scoring_compare_profiles_raw, list):
        scoring_compare_profiles = [str(item).strip() for item in scoring_compare_profiles_raw if str(item).strip()]
    else:
        scoring_compare_profiles = []
    scoring_prompt_info = load_node_prompt(
        node_id="scoring",
        fallback_text=(
            "Calcula score por tipología de fraude usando hypotheses + findings + acfe_snippets "
            "y devuelve ScoreSchema válido."
        ),
        registry_path=metadata.get("prompt_registry_path"),
    )
    scoring_prompt_text = str(scoring_prompt_info.get("text", ""))
    metadata["scoring_prompt_path"] = str(scoring_prompt_info.get("path", "")).strip()
    metadata["scoring_prompt_version"] = str(scoring_prompt_info.get("version", "")).strip()
    metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip()
    metadata["scoring_prompt_status"] = str(scoring_prompt_info.get("status", "")).strip()

    if not findings:
        state.ranking = []
        state.fraud_type_predicho = []
        empty_score = ScoringAgent(model_used="scoring-node-no-findings").parse_output(
            ScoringAgent(model_used="scoring-node-no-findings").generate(
                hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
                findings=[],
                acfe_snippets=[],
            )
        )
        state.scores = [
            {
                **empty_score,
                "ranking": [],
                "fraud_type_distribution": {},
                "summary": {
                    "entities_scored": 0,
                    "findings_total": 0,
                    "top_k": int(top_k_override) if isinstance(top_k_override, int) and top_k_override > 0 else 0,
                },
                "method": "llm_score_schema",
                "source": "scoring_node",
            }
        ]
        metadata["scoring_status"] = "NO_FINDINGS"
        metadata["scoring_entities"] = 0
        metadata["scoring_model_used"] = str(empty_score.get("model_used", "")).strip()
        _record_graph_node_model_config(
            node_id="scoring",
            metadata=metadata,
            default_model_used=str(empty_score.get("model_used", "")).strip() or "scoring-node-no-findings",
            overrides={
                "mode": "stub",
                "model_used": str(empty_score.get("model_used", "")).strip() or "scoring-node-no-findings",
                "temperature": 0.0,
                "max_tokens": 0,
                "profile": str(scoring_model_profile).strip(),
            },
        )
        metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip() or _sha256_text(
            scoring_prompt_text
        )
        metadata["scoring_score_hash"] = _sha256_text(_stable_json(state.scores[0]))
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

    findings_by_fraud_type: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fraud_type = str(finding.get("fraud_type", "")).strip()
        if not fraud_type:
            continue
        entry = findings_by_fraud_type.setdefault(
            fraud_type,
            {
                "finding_count_total": 0,
                "test_ids": set(),
                "hypothesis_ids": set(),
                "acfe_chunks": set(),
            },
        )
        entry["finding_count_total"] += int(finding.get("finding_count", 0) or 0)
        test_id = str(finding.get("test_id", "")).strip()
        if test_id:
            entry["test_ids"].add(test_id)

    selected_tests = [row for row in state.selected_tests if isinstance(row, dict)]
    for row in selected_tests:
        test_id = str(row.get("test_id", "")).strip()
        hypothesis_id = str(row.get("hypothesis_id", "")).strip()
        if not test_id:
            continue
        for fraud_type, entry in findings_by_fraud_type.items():
            if test_id in entry["test_ids"] and hypothesis_id:
                entry["hypothesis_ids"].add(hypothesis_id)

    for explanation in state.explanations:
        if not isinstance(explanation, dict):
            continue
        fraud_type = str(explanation.get("fraud_type", "")).strip()
        if fraud_type not in findings_by_fraud_type:
            continue
        acfe_reference = explanation.get("acfe_reference", {})
        if not isinstance(acfe_reference, dict):
            continue
        hits = acfe_reference.get("hits", [])
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            chunk_id = str(hit.get("chunk_id", "")).strip()
            if chunk_id:
                findings_by_fraud_type[fraud_type]["acfe_chunks"].add(chunk_id)

    acfe_snippets: list[dict[str, Any]] = []
    for fraud_type in sorted(findings_by_fraud_type.keys()):
        for chunk_id in sorted(findings_by_fraud_type[fraud_type]["acfe_chunks"]):
            acfe_snippets.append({"fraud_type": fraud_type, "chunk_id": chunk_id})

    resolved_model_used = str(metadata.get("scoring_model", "")).strip()
    if not resolved_model_used:
        try:
            models_cfg = load_models_config(models_config_path)
            resolved_model = resolve_scoring_model(models_config=models_cfg, profile=scoring_model_profile)
            resolved_model_used = str(resolved_model.get("model_used", "")).strip() or "scoring-stub-v2"
            metadata["scoring_model_profile"] = str(resolved_model.get("profile", "")).strip()
            metadata["scoring_model_temperature"] = float(resolved_model.get("temperature", 0.0) or 0.0)
            metadata["scoring_model_max_tokens"] = int(resolved_model.get("max_tokens", 0) or 0)
            metadata["scoring_models_config"] = models_config_path
        except Exception:
            resolved_model_used = "scoring-stub-v2"
    scoring_agent = ScoringAgent(model_used=resolved_model_used)
    base_score_schema = scoring_agent.parse_output(
        scoring_agent.generate(
            hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
            findings=findings,
            acfe_snippets=acfe_snippets,
        )
    )
    fraud_type_probs: list[dict[str, Any]] = []
    for row in base_score_schema.get("fraud_type_probs", []):
        if not isinstance(row, dict):
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        entry = findings_by_fraud_type.get(fraud_type, {})
        enriched = dict(row)
        enriched["evidence_summary"] = (
            f"support={int(entry.get('finding_count_total', 0) or 0)}; "
            f"tests={sorted(entry.get('test_ids', set()))}; "
            f"hypotheses={sorted(entry.get('hypothesis_ids', set()))}"
        )
        enriched["source_hypothesis_ids"] = sorted(entry.get("hypothesis_ids", set()))
        enriched["acfe_chunk_ids"] = sorted(entry.get("acfe_chunks", set()))
        fraud_type_probs.append(enriched)
    base_score_schema["fraud_type_probs"] = fraud_type_probs
    state.fraud_type_predicho = [
        {"fraud_type": row["fraud_type"], "prob": row["probability"]}
        for row in fraud_type_probs
        if isinstance(row, dict)
    ]
    state.ranking = [dict(row) for row in top_rows if isinstance(row, dict)]

    scores_payload = [
        {
            **base_score_schema,
            "ranking": top_rows,
            "fraud_type_distribution": dict(sorted(fraud_type_distribution.items(), key=lambda item: item[0])),
            "summary": {
                "entities_scored": len(ranking_rows),
                "entities_returned": len(top_rows),
                "findings_total": sum(int(row.get("finding_count", 0) or 0) for row in findings),
                "top_k": top_k,
                "weights_config": weights_config_path,
                "fraud_types_scored": len(fraud_type_probs),
            },
            "method": "llm_score_schema",
            "source": "scoring_node",
        }
    ]

    def _autocorrect_score_payload(
        payload: dict[str, Any],
        *,
        findings_payload: list[dict[str, Any]],
    ) -> dict[str, Any]:
        corrected = dict(payload)
        probs_raw = corrected.get("fraud_type_probs", [])
        probs = [dict(row) for row in probs_raw if isinstance(row, dict)]
        total = sum(max(0.0, float(row.get("probability", 0.0) or 0.0)) for row in probs)
        if probs and total > 0:
            for row in probs:
                row["probability"] = max(0.0, float(row.get("probability", 0.0) or 0.0)) / total
        corrected["fraud_type_probs"] = probs

        known_labels = [str(row.get("fraud_type", "")).strip() for row in probs if str(row.get("fraud_type", "")).strip()]
        final_label = str(corrected.get("final_label", "")).strip()
        if not final_label or final_label not in known_labels:
            winner = max(probs, key=lambda row: float(row.get("probability", 0.0) or 0.0), default={})
            corrected["final_label"] = str(winner.get("fraud_type", "")).strip() or "unknown"

        all_test_ids = sorted(
            {
                str(row.get("test_id", "")).strip()
                for row in findings_payload
                if isinstance(row, dict) and str(row.get("test_id", "")).strip()
            }
        )
        evidence_summary = str(corrected.get("evidence_summary", "")).strip()
        if all_test_ids and not any(test_id in evidence_summary for test_id in all_test_ids):
            corrected["evidence_summary"] = f"Evidence from tests: {', '.join(all_test_ids)}"

        try:
            corrected["confidence"] = max(0.0, min(1.0, float(corrected.get("confidence", 0.0) or 0.0)))
        except (TypeError, ValueError):
            corrected["confidence"] = 0.0
        return corrected

    def _generate_scores(
        _prompt: str,
        input_payload: dict[str, Any],
        repair_feedback: list[str],
        iteration: int,
    ) -> list[dict[str, Any]]:
        base = dict(scores_payload[0]) if scores_payload and isinstance(scores_payload[0], dict) else {}
        if iteration == 1 and not repair_feedback and simulate_invalid_once and base:
            # Fuerza un primer intento inválido para probar la ruta de autocorrección.
            bad = dict(base)
            bad["final_label"] = "invalid_label"
            bad["evidence_summary"] = "No references"
            bad_probs = [dict(row) for row in bad.get("fraud_type_probs", []) if isinstance(row, dict)]
            if bad_probs:
                for row in bad_probs:
                    row["probability"] = float(row.get("probability", 0.0) or 0.0) * 1.1
                bad["fraud_type_probs"] = bad_probs
            return [bad]

        if repair_feedback and base:
            findings_payload = input_payload.get("findings", [])
            if not isinstance(findings_payload, list):
                findings_payload = []
            repaired = _autocorrect_score_payload(base, findings_payload=[row for row in findings_payload if isinstance(row, dict)])
            return [repaired]

        return [base]

    state.scores = _run_alpha_loop_for_node(
        state=state,
        node_id="scoring",
        prompt_text=scoring_prompt_text,
        input_payload={
            "hypotheses": [row for row in state.hypotheses if isinstance(row, dict)],
            "findings_count": len(findings),
            "findings": findings,
            "acfe_snippets": acfe_snippets,
            "top_k": top_k,
        },
        generate_fn=_generate_scores,
        validators={
            "scores_schema": _validate_scores_output,
            "scores_probabilities": _validate_scoring_evidence_and_probability_sum,
        },
        max_iter=2,
    )
    metadata["scoring_status"] = "OK"
    metadata["scoring_entities"] = len(ranking_rows)
    metadata["scoring_top_k"] = top_k
    metadata["scoring_fraud_types"] = len(fraud_type_probs)
    metadata["scoring_model_used"] = str(base_score_schema.get("model_used", "")).strip()
    _record_graph_node_model_config(
        node_id="scoring",
        metadata=metadata,
        default_model_used=str(base_score_schema.get("model_used", "")).strip() or "scoring-stub-v2",
        overrides={
            "mode": "stub",
            "model_used": str(base_score_schema.get("model_used", "")).strip() or "scoring-stub-v2",
            "temperature": float(metadata.get("scoring_model_temperature", 0.0) or 0.0),
            "max_tokens": int(metadata.get("scoring_model_max_tokens", 0) or 0),
            "profile": str(metadata.get("scoring_model_profile", "")).strip(),
        },
    )
    metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip() or _sha256_text(
        scoring_prompt_text
    )
    metadata["scoring_score_hash"] = _sha256_text(_stable_json(state.scores[0] if state.scores else {}))

    if len(scoring_compare_profiles) >= 2:
        try:
            models_cfg = load_models_config(models_config_path)
            baseline_profile = scoring_compare_profiles[0]
            candidate_profile = scoring_compare_profiles[1]
            baseline_model = resolve_scoring_model(models_config=models_cfg, profile=baseline_profile)
            candidate_model = resolve_scoring_model(models_config=models_cfg, profile=candidate_profile)
            baseline_agent = ScoringAgent(model_used=str(baseline_model.get("model_used", "")).strip())
            candidate_agent = ScoringAgent(model_used=str(candidate_model.get("model_used", "")).strip())
            baseline_score = baseline_agent.parse_output(
                baseline_agent.generate(
                    hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
                    findings=findings,
                    acfe_snippets=acfe_snippets,
                )
            )
            candidate_score = candidate_agent.parse_output(
                candidate_agent.generate(
                    hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
                    findings=findings,
                    acfe_snippets=acfe_snippets,
                )
            )
            baseline_probs = {
                str(row.get("fraud_type", "")).strip(): float(row.get("probability", 0.0) or 0.0)
                for row in baseline_score.get("fraud_type_probs", [])
                if isinstance(row, dict) and str(row.get("fraud_type", "")).strip()
            }
            candidate_probs = {
                str(row.get("fraud_type", "")).strip(): float(row.get("probability", 0.0) or 0.0)
                for row in candidate_score.get("fraud_type_probs", [])
                if isinstance(row, dict) and str(row.get("fraud_type", "")).strip()
            }
            fraud_types = sorted(set(baseline_probs.keys()) | set(candidate_probs.keys()))
            deltas = [
                {
                    "fraud_type": fraud_type,
                    "baseline_probability": float(baseline_probs.get(fraud_type, 0.0)),
                    "candidate_probability": float(candidate_probs.get(fraud_type, 0.0)),
                    "delta_probability": float(candidate_probs.get(fraud_type, 0.0))
                    - float(baseline_probs.get(fraud_type, 0.0)),
                }
                for fraud_type in fraud_types
            ]
            score_compare = {
                "version": "1.0.0",
                "baseline_profile": str(baseline_model.get("profile", baseline_profile)).strip(),
                "candidate_profile": str(candidate_model.get("profile", candidate_profile)).strip(),
                "baseline_model_used": str(baseline_score.get("model_used", "")).strip(),
                "candidate_model_used": str(candidate_score.get("model_used", "")).strip(),
                "baseline_final_label": str(baseline_score.get("final_label", "")).strip(),
                "candidate_final_label": str(candidate_score.get("final_label", "")).strip(),
                "baseline_confidence": float(baseline_score.get("confidence", 0.0) or 0.0),
                "candidate_confidence": float(candidate_score.get("confidence", 0.0) or 0.0),
                "confidence_delta": float(candidate_score.get("confidence", 0.0) or 0.0)
                - float(baseline_score.get("confidence", 0.0) or 0.0),
                "final_label_changed": str(baseline_score.get("final_label", "")).strip()
                != str(candidate_score.get("final_label", "")).strip(),
                "deltas_by_fraud_type": deltas,
            }
            metadata["score_compare"] = score_compare
            metadata["scoring_compare_status"] = "OK"
            metadata["scoring_compare_profiles"] = [
                str(baseline_model.get("profile", baseline_profile)).strip(),
                str(candidate_model.get("profile", candidate_profile)).strip(),
            ]
        except Exception as exc:
            metadata["scoring_compare_status"] = f"ERROR: {type(exc).__name__}: {exc}"

    # RF18-09: integración LangSmith opcional/no bloqueante (sin depender de RF14b).
    ls = _langsmith_snapshot()
    score_compare_payload = metadata.get("score_compare")
    if not isinstance(score_compare_payload, dict) or not score_compare_payload:
        metadata["scoring_experiment"] = {
            "status": "SKIPPED",
            "reason": "missing_score_compare",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "langsmith": ls,
        }
    elif not (bool(ls.get("tracing_enabled")) and bool(ls.get("api_key_present")) and str(ls.get("project", "")).strip()):
        metadata["scoring_experiment"] = {
            "status": "SKIPPED",
            "reason": "langsmith_not_configured",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "score_compare_hash": _sha256_text(_stable_json(score_compare_payload)),
            "langsmith": ls,
        }
    else:
        metadata["scoring_experiment"] = {
            "status": "READY",
            "reason": "",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "score_compare_hash": _sha256_text(_stable_json(score_compare_payload)),
            "trace_link": str(ls.get("trace_link", "")).strip(),
            "langsmith": ls,
        }
    return state


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_explanations_markdown(path: Path, explanations: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["# Explanations", ""]
    if not explanations:
        lines.extend(["No explanations generated.", ""])
    else:
        for idx, row in enumerate(explanations, start=1):
            if not isinstance(row, dict):
                continue
            test_id = str(row.get("test_id", "")).strip() or "<unknown_test>"
            status = str(row.get("status", "")).strip() or "UNKNOWN"
            fraud_type = str(row.get("fraud_type", "")).strip() or "unknown"
            finding_count = int(row.get("finding_count", 0) or 0)
            summary = str(row.get("summary", "")).strip()
            evidence_cols = _normalize_columns(row.get("cited_evidence_columns", []))
            keys_payload = row.get("cited_keys", {})
            if not isinstance(keys_payload, dict):
                keys_payload = {}
            lines.append(f"## {idx}. {test_id}")
            lines.append(f"- status: `{status}`")
            lines.append(f"- fraud_type: `{fraud_type}`")
            lines.append(f"- finding_count: `{finding_count}`")
            lines.append(f"- cited_evidence_columns: `{', '.join(evidence_cols) if evidence_cols else '-'}`")
            if keys_payload:
                lines.append(f"- cited_keys: `{json.dumps(keys_payload, ensure_ascii=False, sort_keys=True)}`")
            if summary:
                lines.append(f"- summary: {summary}")
            acfe_reference = row.get("acfe_reference", {})
            if isinstance(acfe_reference, dict):
                acfe_status = str(acfe_reference.get("status", "")).strip()
                if acfe_status:
                    lines.append(f"- acfe_reference_status: `{acfe_status}`")
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


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
        "explanation_json": graph_dir / "explanation.json",
        "explanation_md": graph_dir / "explanation.md",
        "explanations_json": graph_dir / "explanations.json",
        "explanations_md": graph_dir / "explanations.md",
        "score_json": graph_dir / "score.json",
        "scores_json": graph_dir / "scores.json",
        "graph_state_json": graph_dir / "graph_state.json",
        "manifest_json": graph_dir / "manifest.json",
    }
    score_compare_payload = metadata.get("score_compare")
    if isinstance(score_compare_payload, dict) and score_compare_payload:
        paths["score_compare_json"] = graph_dir / "score_compare.json"
    score_experiment_payload = metadata.get("scoring_experiment")
    if isinstance(score_experiment_payload, dict) and score_experiment_payload:
        paths["score_experiment_json"] = graph_dir / "score_experiment.json"

    _write_json(paths["hypotheses_json"], state.hypotheses)
    _write_json(paths["selected_tests_json"], state.selected_tests)
    _write_json(paths["findings_json"], state.findings)
    _write_json(paths["explanation_json"], state.explanations)
    _write_json(paths["explanations_json"], state.explanations)
    _write_explanations_markdown(
        paths["explanation_md"],
        [row for row in state.explanations if isinstance(row, dict)],
    )
    _write_explanations_markdown(
        paths["explanations_md"],
        [row for row in state.explanations if isinstance(row, dict)],
    )
    _write_json(paths["score_json"], state.scores)
    _write_json(paths["scores_json"], state.scores)
    if "score_compare_json" in paths and isinstance(score_compare_payload, dict):
        _write_json(paths["score_compare_json"], score_compare_payload)
    if "score_experiment_json" in paths and isinstance(score_experiment_payload, dict):
        _write_json(paths["score_experiment_json"], score_experiment_payload)

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
