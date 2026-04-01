"""Nodos de planificación (hipótesis/tests) y validadores."""

from __future__ import annotations

# ruff: noqa: F401,F403,F405,F821

from . import _legacy as _legacy

globals().update(vars(_legacy))

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
