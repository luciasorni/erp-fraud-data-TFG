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
    explanation_for_test,
    extract_score_value,
    findings_table_rows,
    recommendations_for_finding,
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


def test_rf20_ui_mappers_fill_missing_process_step_and_hypothesis_from_selected_test() -> None:
    findings = findings_table_rows(
        [
            {
                "id": "TST-O2C-DISCOUNT-POLICY-BREACH",
                "title": "TST-O2C-DISCOUNT-POLICY-BREACH",
                "summary": "0 hallazgos detectados",
                "status": "SKIPPED",
                "subtitle": "",
                "attributes": {
                    "finding_count": 0,
                    "error_summary": "LOW_APPLICABILITY",
                },
            }
        ],
        selected_tests=[
            {
                "id": "TST-O2C-DISCOUNT-POLICY-BREACH",
                "subtitle": "HYP-003",
                "attributes": {
                    "hypothesis_id": "HYP-003",
                },
            }
        ],
    )
    assert findings[0]["hypothesis_id"] == "HYP-003"
    assert findings[0]["summary"] == "LOW_APPLICABILITY"
    assert findings[0]["process_step"] != "No disponible en este run"


def test_rf20_ui_mappers_prioritize_drilldownable_findings() -> None:
    findings = findings_table_rows(
        [
            {
                "id": "TST-O2C-CLEARING-ANOMALY",
                "title": "TST-O2C-CLEARING-ANOMALY",
                "status": "OK",
                "attributes": {
                    "finding_count": 0,
                    "rows": [],
                    "drilldown_ready": False,
                },
            },
            {
                "id": "TST-O2C-DELIVERY-QUANTITY-MISMATCH",
                "title": "TST-O2C-DELIVERY-QUANTITY-MISMATCH",
                "status": "OK",
                "attributes": {
                    "finding_count": 3,
                    "sample_keys": {"delivery_id": "80001736", "delivery_item_id": "30"},
                    "sample_query_id": "drilldown_o2c_delivery_quantity_mismatch_v1",
                    "rows": [
                        {
                            "keys": {"delivery_id": "80001736", "delivery_item_id": "30"},
                            "query_id": "drilldown_o2c_delivery_quantity_mismatch_v1",
                        }
                    ],
                    "drilldown_ready": True,
                },
            },
        ]
    )

    assert findings[0]["test_id"] == "TST-O2C-DELIVERY-QUANTITY-MISMATCH"
    assert findings[0]["drilldown_ready"] is True
    assert findings[1]["test_id"] == "TST-O2C-CLEARING-ANOMALY"


def test_rf20_ui_mappers_build_fallback_explanation_from_finding_and_catalog() -> None:
    explanation = explanation_for_test(
        [],
        "TST-O2C-DISCOUNT-POLICY-BREACH",
        findings=[
            {
                "id": "TST-O2C-DISCOUNT-POLICY-BREACH",
                "status": "SKIPPED",
                "attributes": {
                    "finding_count": 0,
                    "error_summary": "LOW_APPLICABILITY",
                },
            }
        ],
        selected_tests=[],
    )
    assert explanation is not None
    assert explanation["test_id"] == "TST-O2C-DISCOUNT-POLICY-BREACH"
    assert explanation["summary"] == "LOW_APPLICABILITY"
    assert explanation["fraud_type"] != "No disponible en este run"
    assert explanation["process_step"] != "No disponible en este run"


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


def test_rf20_ui_recommendations_panel_reads_body_and_metadata_from_attributes() -> None:
    item = {
        "title": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
        "status": "recommended_test",
        "attributes": {
            "section": "recommended_tests",
            "why": "Contrasta la señal principal del hallazgo actual.",
            "owner": "Analítica",
        },
    }
    body = _body_text_for_item(item, title=item["title"], subtitle="")
    assert body == "Contrasta la señal principal del hallazgo actual."


def test_rf20_ui_recommendations_panel_hides_duplicate_test_id_from_attributes() -> None:
    cleaned = _clean_attributes_for_display(
        {
            "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
            "source": "planner_llm",
            "process_step": "invoice_posting",
        }
    )
    assert "test_id" not in cleaned
    assert cleaned["source"] == "planner_llm"


def test_rf20_ui_mappers_enrich_recommended_tests_with_context() -> None:
    items = recommendations_for_finding(
        [
            {
                "title": "Test recomendado 1",
                "summary": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                "status": "recommended_test",
                "section": "recommended_tests",
                "attributes": {},
            }
        ],
        finding={"test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR"},
        selected_tests=[
            {
                "id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
                "summary": "Coincide con la hipótesis principal.",
                "attributes": {"hypothesis_id": "HYP-001", "process_step": "invoice_posting"},
            }
        ],
        explanations=[],
    )
    assert items[0]["title"] == "TST-UNUSUAL-AMOUNT-BY-VENDOR"
    assert "Coincide con la hipótesis principal." in items[0]["summary"]
    assert items[0]["attributes"]["relation_to_current_finding"] == "Corresponde al test del hallazgo actual."
