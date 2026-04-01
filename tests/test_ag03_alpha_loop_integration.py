from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import src.erp_fraud.graph.nodes as nodes
from src.erp_fraud.graph import (
    create_initial_graph_state,
    explainer_node,
    hypothesis_planner_node,
    scoring_node,
    test_planner_node,
)


def test_ag03_09_integrates_alpha_loop_in_llm_nodes(monkeypatch: Any) -> None:
    calls: list[str] = []

    def _fake_alpha_loop(**kwargs: Any) -> Any:
        output = kwargs["generate_fn"](
            kwargs["prompt_text"],
            dict(kwargs["input_payload"]),
            [],
            1,
        )
        for validator in kwargs["validators"].values():
            result = validator(output, dict(kwargs["input_payload"]))
            assert bool(result.get("passed", False)), result
        calls.append(str(kwargs["node_id"]))
        return SimpleNamespace(
            status="OK",
            run_id=str(kwargs["run_id"]),
            node_id=str(kwargs["node_id"]),
            iterations=1,
            final_output=output,
            last_validation={"validation_passed": True, "checks": []},
            artifacts_dir=f"run_results/{kwargs['run_id']}/alphacodium/{kwargs['node_id']}",
        )

    monkeypatch.setattr(nodes, "alpha_loop", _fake_alpha_loop)
    monkeypatch.setattr(
        nodes,
        "alpha_loop_result_to_dict",
        lambda result: {
            "status": result.status,
            "iterations": result.iterations,
            "artifacts_dir": result.artifacts_dir,
        },
    )

    state_h = create_initial_graph_state(run_id="ag03-09-h")
    state_h.schema = {"table_count": 1, "tables": [{"table_name": "fraud_1", "columns": [{"name": "Kreditor"}]}]}
    state_h.run_metadata["catalog_path"] = "tests/catalog"
    out_h = hypothesis_planner_node(state_h)
    assert len(out_h.hypotheses) >= 1

    state_t = create_initial_graph_state(run_id="ag03-09-t")
    state_t.run_metadata["catalog_path"] = "tests/catalog"
    state_t.hypotheses = [{"hypothesis_id": "HYP-001", "title": "Split payments near threshold"}]
    out_t = test_planner_node(state_t)
    assert len(out_t.selected_tests) >= 1

    state_e = create_initial_graph_state(run_id="ag03-09-e")
    state_e.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "status": "OK",
            "fraud_type": "duplicate_payment",
            "finding_count": 1,
            "columns": ["kreditor", "belegnummer"],
            "rows": [{"entity_key": "kreditor=V1|belegnummer=D1"}],
        }
    ]
    out_e = explainer_node(state_e)
    assert len(out_e.explanations) == 1

    state_s = create_initial_graph_state(run_id="ag03-09-s")
    state_s.run_metadata["weights_config"] = "config/weights.yaml"
    state_s.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "test_version": "1.0.0",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 1,
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "duplicate_count"],
                    "metrics": {"duplicate_count": 2},
                }
            ],
        }
    ]
    out_s = scoring_node(state_s)
    assert len(out_s.scores) == 1

    assert set(calls) == {"hypothesis_planner", "test_planner", "expert_explainer", "scoring"}

