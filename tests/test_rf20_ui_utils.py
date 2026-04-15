from __future__ import annotations

from app.ui.utils.formatters import format_bool, format_bytes, format_scope, format_status
from app.ui.utils.mappers import build_execution_metrics, build_run_kpis, findings_table_rows


def test_rf20_ui_formatters_render_expected_labels() -> None:
    assert format_scope("both") == "P2P + O2C"
    assert format_status("COMPLETED") == "Completada"
    assert format_bool(True) == "Sí"
    assert format_bytes(1024) == "1.0 KB"


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
                },
            }
        ]
    )
    assert findings[0]["finding_id"] == "TST-001"
    assert findings[0]["sample_keys"]["doc"] == "1"

