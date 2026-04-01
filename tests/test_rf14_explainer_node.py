from __future__ import annotations

import pytest

from src.erp_fraud.graph import create_initial_graph_state, explainer_node
from src.erp_fraud.graph.nodes import _validate_explanations_guardrails


def test_rf14_explainer_node_builds_guarded_explanations_from_findings() -> None:
    state = create_initial_graph_state(run_id="rf14-08-ok")
    state.findings = [
        {
            "test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT",
            "fraud_type": "authorization_bypass",
            "status": "OK",
            "finding_count": 2,
            "columns": ["kreditor", "belegnummer", "total_betrag"],
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "total_betrag"],
                }
            ],
        }
    ]

    out = explainer_node(state)

    assert out.run_metadata["explainer_status"] == "OK"
    assert out.run_metadata["explainer_explanations_count"] == 1
    assert len(out.explanations) == 1
    assert out.explanations[0]["test_id"] == "TST-SPLIT-PAYMENTS-NEAR-LIMIT"
    assert out.explanations[0]["finding_count"] == 2
    assert out.explanations[0]["sample_entity_key"] == "kreditor=V1|belegnummer=D1"
    assert "kreditor" in out.explanations[0]["referenced_columns"]
    assert out.explanations[0]["cited_test_id"] == "TST-SPLIT-PAYMENTS-NEAR-LIMIT"
    assert out.explanations[0]["cited_keys"]["kreditor"] == "V1"
    assert "kreditor" in out.explanations[0]["cited_evidence_columns"]
    assert out.explanations[0]["acfe_reference"]["status"] == "SKIPPED"


def test_rf14_explainer_node_no_findings_message() -> None:
    state = create_initial_graph_state(run_id="rf14-08-empty")
    state.findings = []

    out = explainer_node(state)

    assert out.run_metadata["explainer_status"] == "NO_FINDINGS"
    assert len(out.explanations) == 1
    assert out.explanations[0]["status"] == "NO_DATA"
    assert out.explanations[0]["cited_keys"] == {}


def test_rf14_explainer_guardrail_rejects_unknown_columns() -> None:
    findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "columns": ["kreditor", "betrag"],
            "rows": [
                {
                    "keys": {"kreditor": "V1"},
                    "evidence_columns": ["kreditor", "betrag"],
                }
            ],
        }
    ]
    explanations = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "cited_test_id": "TST-DUPLICATE-POSTINGS",
            "referenced_columns": ["kreditor", "NO_EXISTE"],
            "cited_keys": {"kreditor": "V1"},
            "cited_evidence_columns": ["kreditor"],
        }
    ]

    with pytest.raises(ValueError, match="columnas no presentes"):
        _validate_explanations_guardrails(explanations=explanations, findings=findings)


def test_rf14_explainer_guardrail_rejects_unknown_cited_keys() -> None:
    findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "columns": ["kreditor", "betrag"],
            "rows": [
                {
                    "keys": {"kreditor": "V1"},
                    "evidence_columns": ["kreditor", "betrag"],
                }
            ],
        }
    ]
    explanations = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "cited_test_id": "TST-DUPLICATE-POSTINGS",
            "referenced_columns": ["kreditor"],
            "cited_keys": {"belegnummer": "D1"},
            "cited_evidence_columns": ["kreditor"],
        }
    ]

    with pytest.raises(ValueError, match="keys inexistentes"):
        _validate_explanations_guardrails(explanations=explanations, findings=findings)
