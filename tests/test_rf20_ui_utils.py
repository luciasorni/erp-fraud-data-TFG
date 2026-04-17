from __future__ import annotations

from app.ui.utils.formatters import (
    format_bool,
    format_bytes,
    format_datetime,
    format_scope,
    format_status,
    normalize_structured_content,
    summarize_structured_content,
)
from app.ui.components.recommendations_panel import (
    _body_text_for_item,
    _clean_attributes_for_display,
    _fallback_detail_text,
)
from app.ui.utils.mappers import (
    build_execution_metrics,
    build_run_kpis,
    extract_score_value,
    findings_table_rows,
    split_recommendation_sections,
)


def test_rf20_ui_formatters_render_expected_labels() -> None:
    assert format_scope("both") == "P2P + O2C"
    assert format_status("COMPLETED") == "Completada"
    assert format_bool(True) == "Sí"
    assert format_bytes(1024) == "1.0 KB"
    assert format_datetime("2026-04-15T10:00:00+00:00") == "15/04/2026 12:00"


def test_rf20_ui_mappers_generate_metrics_and_findings_rows() -> None:
    metrics = build_execution_metrics(
        [
            {"status": "COMPLETED"},
            {"status": "FAILED"},
            {"status": "RUNNING"},
        ]
    )
    assert metrics == {"total": 3, "completed": 1, "running": 1, "failed": 1}

    kpis = build_run_kpis({"counts": {"hypotheses": 2, "selected_tests": 3, "findings": 4, "scores": 1}})
    assert kpis["findings"] == 4

    findings = findings_table_rows(
        [
            {
                "id": "TST-001",
                "title": "Duplicate posting",
                "summary": "2 findings",
                "status": "OK",
                "subtitle": "duplicate_posting",
                "attributes": {
                    "finding_count": 2,
                    "sample_entity_key": "x",
                    "sample_keys": {"doc": "1"},
                    "sample_query_id": "drilldown_x_v1",
                    "required_keys": ["doc"],
                    "missing_keys": [],
                    "drilldown_ready": True,
                    "drilldown_error": None,
                },
            }
        ]
    )
    assert findings[0]["finding_id"] == "TST-001"
    assert findings[0]["sample_keys"]["doc"] == "1"
    assert findings[0]["sample_query_id"] == "drilldown_x_v1"
    assert findings[0]["drilldown_ready"] is True


def test_rf20_ui_mappers_extract_score_and_split_recommendations() -> None:
    score = extract_score_value({"attributes": {"confidence": 0.82}, "subtitle": "confidence=0.20"})
    assert score == 0.82

    sections = split_recommendation_sections(
        [
            {"status": "recommended_action", "summary": "review"},
            {"status": "recommended_test", "summary": "retest"},
            {"status": "audit_procedure", "summary": "audit"},
        ]
    )
    assert len(sections["recommendations"]) == 1
    assert len(sections["recommended_tests"]) == 1
    assert len(sections["audit_procedures"]) == 1


def test_rf20_ui_normalize_structured_content_handles_real_dict_and_list() -> None:
    assert normalize_structured_content({"key_evidence": ["a", "b"]}) == {"key_evidence": ["a", "b"]}
    assert normalize_structured_content(["a", "b"]) == ["a", "b"]


def test_rf20_ui_normalize_structured_content_parses_json_string() -> None:
    parsed = normalize_structured_content('{"overall_assessment":"ok","key_evidence":["a"]}')
    assert parsed == {"overall_assessment": "ok", "key_evidence": ["a"]}


def test_rf20_ui_normalize_structured_content_parses_python_repr_string() -> None:
    parsed = normalize_structured_content("{'risk_posture': 'Moderado', 'key_evidence': ['uno', 'dos']}")
    assert parsed == {"risk_posture": "Moderado", "key_evidence": ["uno", "dos"]}


def test_rf20_ui_normalize_structured_content_falls_back_to_text() -> None:
    text = "No parece JSON pero sí texto útil {sin cerrar"
    assert normalize_structured_content(text) == text
    assert summarize_structured_content(text) == text


def test_rf20_ui_recommendations_panel_hides_technical_section_from_context() -> None:
    cleaned = _clean_attributes_for_display(
        {
            "section": "recommendations",
            "runs_compared": ["run-1"],
            "status": "recommended_action",
        }
    )
    assert cleaned == {"runs_compared": ["run-1"]}


def test_rf20_ui_recommendations_panel_avoids_empty_body_and_uses_fallback_text() -> None:
    item = {
        "title": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
        "summary": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
        "section": "recommended_tests",
    }
    body = _body_text_for_item(item, title=item["title"], subtitle=item["summary"])
    assert body == ""
    fallback = _fallback_detail_text(item=item, body_text=body, evidence=[], attributes={})
    assert "Test sugerido" in fallback
