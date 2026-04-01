from __future__ import annotations

from pathlib import Path

import pytest

from src.erp_fraud.graph import create_initial_graph_state, persist_node
from src.erp_fraud.graph.nodes import _validate_explanations_guardrails


def test_rf15_07_validator_rejects_false_column_reference() -> None:
    findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "columns": ["kreditor", "belegnummer", "betrag"],
            "rows": [
                {
                    "keys": {"kreditor": "V-100", "belegnummer": "D-0001"},
                    "evidence_columns": ["kreditor", "belegnummer", "betrag"],
                }
            ],
        }
    ]
    explanations = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "cited_test_id": "TST-DUPLICATE-POSTINGS",
            "referenced_columns": ["kreditor", "columna_falsa"],
            "cited_keys": {"kreditor": "V-100", "belegnummer": "D-0001"},
            "cited_evidence_columns": ["kreditor", "belegnummer", "betrag"],
        }
    ]

    with pytest.raises(ValueError, match="columnas no presentes"):
        _validate_explanations_guardrails(explanations=explanations, findings=findings)


def test_rf15_07_explanation_markdown_snapshot(tmp_path: Path) -> None:
    state = create_initial_graph_state(run_id="rf15-07-snapshot")
    state.run_metadata["persist_base_dir"] = str(tmp_path / "run_results")
    state.explanations = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "status": "OK",
            "fraud_type": "duplicate_payment",
            "finding_count": 2,
            "cited_keys": {"kreditor": "V-100", "belegnummer": "D-0001"},
            "cited_evidence_columns": ["kreditor", "belegnummer", "betrag"],
            "summary": "Posible duplicado por mismo proveedor/documento/importe.",
            "acfe_reference": {"status": "HIT", "hits": []},
        }
    ]

    out = persist_node(state)
    graph_dir = Path(str(out.run_metadata["persist_graph_dir"]))
    generated = (graph_dir / "explanation.md").read_text(encoding="utf-8")
    expected = Path("tests/fixtures/rf15/explanation_template_snapshot.md").read_text(encoding="utf-8")

    assert generated == expected
