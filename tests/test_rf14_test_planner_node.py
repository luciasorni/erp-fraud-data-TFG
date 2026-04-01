from __future__ import annotations

from src.erp_fraud.graph import create_initial_graph_state, test_planner_node


def test_rf14_test_planner_selects_allowlisted_tests_from_hypothesis() -> None:
    state = create_initial_graph_state(run_id="rf14-06-select")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["test_planner_top_n"] = 2
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-001",
            "title": "Split payments just below authorization thresholds",
            "description": "Possible authorization bypass in P2P invoices",
        }
    ]

    out = test_planner_node(state)

    assert len(out.selected_tests) >= 1
    selected_ids = {row["test_id"] for row in out.selected_tests}
    assert "TST-SPLIT-PAYMENTS-NEAR-LIMIT" in selected_ids
    assert out.run_metadata["selected_tests_count"] == len(out.selected_tests)


def test_rf14_test_planner_filters_invalid_candidate_test_ids() -> None:
    state = create_initial_graph_state(run_id="rf14-06-candidates")
    state.run_metadata["catalog_path"] = "tests/catalog"
    state.run_metadata["test_planner_top_n"] = 3
    state.hypotheses = [
        {
            "hypothesis_id": "HYP-002",
            "title": "Duplicate postings by vendor",
            "candidate_test_ids": [
                "TST-DUPLICATE-POSTINGS",
                "TST-NOT-EXISTS",
            ],
        }
    ]

    out = test_planner_node(state)

    assert len(out.selected_tests) == 1
    assert out.selected_tests[0]["test_id"] == "TST-DUPLICATE-POSTINGS"
    assert out.selected_tests[0]["source"] == "planner_stub_allowlist"

