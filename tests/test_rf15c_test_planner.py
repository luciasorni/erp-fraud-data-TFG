from __future__ import annotations

from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, test_planner_node


def test_rf15c_test_planner_populates_recommendations_with_allowlist_trace() -> None:
    state = create_initial_graph_state(run_id="rf15c-05-recommendations")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["test_planner_top_n"] = 2
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-001",
            "title": "Split payments near threshold",
            "description": "Potential authorization bypass",
            "fraud_type": "authorization_bypass",
        }
    ]

    out = test_planner_node(state)

    assert out.selected_tests
    assert out.recomendaciones
    selected_ids = {row["test_id"] for row in out.selected_tests if isinstance(row, dict)}
    recommended_ids = {row["test_id"] for row in out.recomendaciones if isinstance(row, dict)}
    assert recommended_ids.issubset(selected_ids)
    assert out.run_metadata["test_planner_allowlist_enforced"] is True
    assert out.run_metadata["recommendations_count"] == len(out.recomendaciones)
    assert all(row.get("approved_for_execution") is False for row in out.recomendaciones)


def test_rf15c_test_planner_never_emits_test_id_outside_catalog_allowlist(
    monkeypatch: Any,
) -> None:
    import src.erp_fraud.graph.nodes as nodes

    def _fake_catalog_tool(*, catalog_path: str) -> dict[str, Any]:
        _ = catalog_path
        return {
            "tests": [
                {
                    "id": "TST-DUPLICATE-POSTINGS",
                    "fraud_type": "duplicate_payment",
                    "process_step": "invoice_posting",
                    "name": "Duplicate postings",
                    "tags": ["duplicates"],
                }
            ],
            "count": 1,
        }

    monkeypatch.setattr(nodes, "_tool_test_catalog", _fake_catalog_tool)

    state = create_initial_graph_state(run_id="rf15c-05-allowlist")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["test_planner_top_n"] = 3
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-002",
            "title": "Potential split and duplicate patterns",
            "description": "mentions TST-SPLIT-PAYMENTS-NEAR-LIMIT explicitly",
            "fraud_type": "authorization_bypass",
            "candidate_test_ids": ["TST-DUPLICATE-POSTINGS", "TST-NOT-IN-CATALOG"],
        }
    ]

    out = test_planner_node(state)

    assert len(out.selected_tests) == 1
    assert out.selected_tests[0]["test_id"] == "TST-DUPLICATE-POSTINGS"
    assert out.recomendaciones[0]["test_id"] == "TST-DUPLICATE-POSTINGS"


def test_rf15c_test_planner_discards_tests_with_required_columns_missing_in_schema(
    monkeypatch: Any,
) -> None:
    import src.erp_fraud.graph.nodes as nodes

    def _fake_catalog_tool(*, catalog_path: str) -> dict[str, Any]:
        _ = catalog_path
        return {
            "tests": [
                {
                    "id": "TST-NEEDS-MISSING-COL",
                    "fraud_type": "duplicate_payment",
                    "process_step": "invoice_posting",
                    "name": "Needs missing col",
                    "table_requirements": [
                        {"table": "fraud_1", "required_columns": ["Kreditor", "NotInSchema"]}
                    ],
                    "tags": ["duplicates"],
                }
            ],
            "count": 1,
        }

    monkeypatch.setattr(nodes, "_tool_test_catalog", _fake_catalog_tool)

    state = create_initial_graph_state(run_id="rf15c-06-schema-filter")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.schema = {
        "schema_name": "main",
        "tables": [{"table_name": "fraud_1", "columns": [{"name": "Kreditor"}]}],
    }
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-010",
            "title": "Any",
            "description": "Any",
            "fraud_type": "duplicate_payment",
        }
    ]

    out = test_planner_node(state)
    assert out.selected_tests == []
    assert out.recomendaciones == []
    assert out.run_metadata["test_planner_schema_filtered_count"] == 1
    reasons = out.run_metadata.get("test_planner_schema_filtered", [])
    assert isinstance(reasons, list) and reasons
    assert "TST-NEEDS-MISSING-COL" in reasons[0]


def test_rf15c_test_planner_accepts_llm_decisions_object_output(monkeypatch: Any) -> None:
    import src.erp_fraud.graph.nodes.planning as planning_mod

    def _fake_runtime_target(**_kwargs: Any) -> dict[str, Any]:
        return {
            "enabled": True,
            "model_used": "gpt-5.4-mini",
            "temperature": 0.0,
            "max_tokens": 256,
            "mode_effective": "real_runtime",
            "provider": "openai",
        }

    def _fake_call_openai_json(**_kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            {
                "status": "OK",
                "decisions": [
                    {
                        "id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT",
                        "hypothesis_id": "HYP-001",
                        "reason": "matches authorization bypass hypothesis",
                        "confidence": 0.87,
                    }
                ],
            },
            {
                "status": "OK",
                "model_used": "gpt-5.4-mini",
                "latency_ms": 1,
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
                "cost_estimated_usd": 0.0,
                "retries_done": 0,
                "fallback_used": False,
            },
        )

    monkeypatch.setattr(planning_mod, "resolve_node_runtime_target", _fake_runtime_target)
    monkeypatch.setattr(planning_mod, "call_openai_json", _fake_call_openai_json)

    state = create_initial_graph_state(run_id="rf15c-05-llm-decisions-object")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["llm_mode"] = "real"
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-001",
            "title": "Split payments near threshold",
            "description": "Potential authorization bypass",
            "fraud_type": "authorization_bypass",
            "process_step": "invoice_posting",
        }
    ]

    out = test_planner_node(state)
    assert out.selected_tests
    assert out.selected_tests[0]["test_id"] == "TST-SPLIT-PAYMENTS-NEAR-LIMIT"
    assert out.selected_tests[0]["source"] == "planner_llm"


def test_rf15c_test_planner_assigns_hypothesis_id_by_fraud_type_when_llm_omits_it(
    monkeypatch: Any,
) -> None:
    import src.erp_fraud.graph.nodes.planning as planning_mod

    def _fake_runtime_target(**_kwargs: Any) -> dict[str, Any]:
        return {
            "enabled": True,
            "model_used": "gpt-5.4-mini",
            "temperature": 0.0,
            "max_tokens": 256,
            "mode_effective": "real_runtime",
            "provider": "openai",
        }

    def _fake_call_openai_json(**_kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            {
                "status": "OK",
                "decisions": [
                    {
                        "id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                        "fraud_type": "amount_anomaly",
                        "reason": "amount anomaly evidence",
                    },
                    {
                        "id": "TST-JUST-BELOW-AUTH-THRESHOLD",
                        "fraud_type": "authorization_bypass",
                        "reason": "authorization threshold pattern",
                    },
                ],
            },
            {
                "status": "OK",
                "model_used": "gpt-5.4-mini",
                "latency_ms": 1,
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
                "cost_estimated_usd": 0.0,
                "retries_done": 0,
                "fallback_used": False,
            },
        )

    monkeypatch.setattr(planning_mod, "resolve_node_runtime_target", _fake_runtime_target)
    monkeypatch.setattr(planning_mod, "call_openai_json", _fake_call_openai_json)

    state = create_initial_graph_state(run_id="rf15c-05-llm-map-hypothesis-id")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["llm_mode"] = "real"
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-001",
            "title": "Amount anomaly",
            "description": "",
            "fraud_type": "amount_anomaly",
            "process_step": "invoice_posting",
        },
        {
            "hypothesis_id": "HYP-002",
            "title": "Authorization bypass",
            "description": "",
            "fraud_type": "authorization_bypass",
            "process_step": "invoice_posting",
        },
    ]

    out = test_planner_node(state)
    selected = {
        (str(row.get("hypothesis_id", "")), str(row.get("test_id", "")))
        for row in out.selected_tests
        if isinstance(row, dict)
    }
    assert ("HYP-001", "TST-UNUSUAL-AMOUNT-BY-VENDOR") in selected
    assert ("HYP-002", "TST-JUST-BELOW-AUTH-THRESHOLD") in selected


def test_rf15c_test_planner_enforces_min_coverage_per_hypothesis_in_real_mode(
    monkeypatch: Any,
) -> None:
    import src.erp_fraud.graph.nodes.planning as planning_mod

    def _fake_runtime_target(**_kwargs: Any) -> dict[str, Any]:
        return {
            "enabled": True,
            "model_used": "gpt-5.4-mini",
            "temperature": 0.0,
            "max_tokens": 256,
            "mode_effective": "real_runtime",
            "provider": "openai",
        }

    def _fake_call_openai_json(**_kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            {
                "status": "OK",
                "decisions": [
                    {
                        "id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                        "hypothesis_id": "HYP-001",
                        "reason": "single decision only",
                    }
                ],
            },
            {
                "status": "OK",
                "model_used": "gpt-5.4-mini",
                "latency_ms": 1,
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
                "cost_estimated_usd": 0.0,
                "retries_done": 0,
                "fallback_used": False,
            },
        )

    monkeypatch.setattr(planning_mod, "resolve_node_runtime_target", _fake_runtime_target)
    monkeypatch.setattr(planning_mod, "call_openai_json", _fake_call_openai_json)

    state = create_initial_graph_state(run_id="rf15c-05-min-coverage")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["llm_mode"] = "real"
    state.run_metadata["test_planner_min_per_hypothesis_real"] = 1
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-001",
            "title": "Amount anomaly",
            "description": "",
            "fraud_type": "amount_anomaly",
            "process_step": "invoice_posting",
        },
        {
            "hypothesis_id": "HYP-002",
            "title": "Authorization bypass",
            "description": "",
            "fraud_type": "authorization_bypass",
            "process_step": "invoice_posting",
        },
    ]

    out = test_planner_node(state)
    by_hyp = {}
    for row in out.selected_tests:
        if not isinstance(row, dict):
            continue
        hyp = str(row.get("hypothesis_id", "")).strip()
        by_hyp[hyp] = by_hyp.get(hyp, 0) + 1
    assert by_hyp.get("HYP-001", 0) >= 1
    assert by_hyp.get("HYP-002", 0) >= 1
    assert int(out.run_metadata.get("test_planner_min_per_hypothesis_real_added", 0) or 0) >= 1
