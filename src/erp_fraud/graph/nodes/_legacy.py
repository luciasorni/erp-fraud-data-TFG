"""Nodos stub del grafo RF14 (tarea RF14-02)."""

from __future__ import annotations

# ruff: noqa: F401

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

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
from .common import (
    langsmith_snapshot as _langsmith_snapshot,
    record_graph_node_model_config as _record_graph_node_model_config,
    resolve_project_path as _resolve_project_path,
    sha256_text as _sha256_text,
    stable_json as _stable_json,
)
from .persist_utils import (
    collect_alphacodium_artifacts as _collect_alphacodium_artifacts,
    normalize_columns as _normalize_columns,
    write_explanations_markdown as _write_explanations_markdown,
    write_json as _write_json,
)
from ..prompt_registry import load_node_prompt
from ..state import GraphState
from ..observability import append_error_event

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
    from .planning import _validate_hypotheses_output as _impl

    return _impl(output, input_payload)

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


def _validate_scoring_evidence_and_probability_sum(
    output: Any, input_payload: dict[str, Any]
) -> dict[str, Any]:
    from .scoring import _validate_scoring_evidence_and_probability_sum as _impl

    return _impl(output, input_payload)

def hypothesis_planner_node(state: GraphState) -> GraphState:
    from .planning import hypothesis_planner_node as _impl

    return _impl(state)

def ingest_node(state: GraphState) -> GraphState:
    from .ingest import ingest_node as _impl

    return _impl(state)

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
    from .planning import test_planner_node as _impl

    return _impl(state)

def kb_index_node(state: GraphState) -> GraphState:
    from .ingest import kb_index_node as _impl

    return _impl(state)

def executor_node(state: GraphState) -> GraphState:
    from .executor import executor_node as _impl

    return _impl(state)

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
    *, explanations: list[dict], findings: list[dict], catalog_test_ids=None, schema_columns=None
):
    from .explainer import _validate_explanations_guardrails as _impl

    return _impl(
        explanations=explanations,
        findings=findings,
        catalog_test_ids=catalog_test_ids,
        schema_columns=schema_columns,
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
    from .explainer import explainer_node as _impl

    return _impl(state)

def expert_explainer_node(state: GraphState) -> GraphState:
    from .explainer import expert_explainer_node as _impl

    return _impl(state)

def scoring_node(state: GraphState) -> GraphState:
    from .scoring import scoring_node as _impl

    return _impl(state)

def persist_node(state: GraphState) -> GraphState:
    from .persist import persist_node as _impl

    return _impl(state)

def run_node_by_id(*, node_id: str, state: GraphState) -> GraphState:
    from .registry import run_node_by_id as _impl

    return _impl(node_id=node_id, state=state)
