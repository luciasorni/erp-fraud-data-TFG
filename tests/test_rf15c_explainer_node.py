from __future__ import annotations

from typing import Any

from src.erp_fraud.graph import create_initial_graph_state, explainer_node


def test_rf15c_explainer_adds_acfe_reference_from_kb_when_enabled(monkeypatch: Any) -> None:
    import src.erp_fraud.graph.nodes as nodes

    class _FakeKBSearchTool:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def search(self, *, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> dict[str, Any]:
            _ = query, top_k, filters
            return {
                "count": 1,
                "hits": [
                    {
                        "chunk_id": "acfe-chunk-1",
                        "score": 0.91,
                        "metadata": {
                            "source_path": "docs/external/data_analytics_tests.pdf",
                            "source_id": "acfe_pdf",
                        },
                    }
                ],
            }

    monkeypatch.setattr(nodes, "KBSearchTool", _FakeKBSearchTool)

    state = create_initial_graph_state(run_id="rf15c-08-explainer-kb")
    state.run_metadata["kb_search_enabled"] = True
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 1,
            "columns": ["kreditor", "betrag"],
            "rows": [
                {
                    "entity_key": "kreditor=V1",
                    "keys": {"kreditor": "V1"},
                    "evidence_columns": ["kreditor", "betrag"],
                }
            ],
        }
    ]

    out = explainer_node(state)
    assert out.run_metadata["explainer_status"] == "OK"
    assert out.run_metadata["explainer_kb_enabled"] is True
    assert len(out.explanations) == 1
    acfe_ref = out.explanations[0]["acfe_reference"]
    assert acfe_ref["status"] == "OK"
    assert acfe_ref["hits"][0]["chunk_id"] == "acfe-chunk-1"
    assert "data_analytics_tests.pdf" in acfe_ref["hits"][0]["source_path"]
