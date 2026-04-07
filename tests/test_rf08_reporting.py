from __future__ import annotations

from pathlib import Path

from src.erp_fraud.storage import (
    build_report_json_payload,
    render_report_markdown_to_html,
    validate_report_json_file_artifact_links,
    write_report_json,
    write_report_markdown_from_report_json,
)


def test_build_report_json_payload_includes_expected_sections() -> None:
    payload = build_report_json_payload(
        run_id="rf08-test",
        dataset_hash="hash-1",
        summary={"overall_status": "OK", "tests_total": 2, "tests_ok": 2},
        ranking=[{"entity_key": "k=1", "score_total": 1.0}],
        top_k=20,
        test_runs=[
            {
                "test_id": "TST-A",
                "version": "1.0.0",
                "status": "OK",
                "duration_ms": 10,
                "error_summary": "",
            }
        ],
    )
    assert payload["report_version"] == "1.0.0"
    assert payload["metadata"]["run_id"] == "rf08-test"
    assert payload["summary"]["tests_total"] == 2
    assert payload["ranking"]["row_count"] == 1
    assert "artifact_paths" in payload


def test_build_report_json_payload_generates_errors_from_test_runs() -> None:
    payload = build_report_json_payload(
        run_id="rf08-test-errors",
        dataset_hash="hash-2",
        test_runs=[
            {
                "test_id": "TST-B",
                "version": "1.0.0",
                "status": "ERROR",
                "duration_ms": 12,
                "error_summary": "RuntimeError: boom",
            }
        ],
    )
    assert payload["errors"] == [
        {
            "scope": "test_run",
            "code": "ERROR:TST-B",
            "message": "RuntimeError: boom",
        }
    ]


def test_write_report_markdown_from_report_json_contains_error_section(tmp_path: Path) -> None:
    report_json_path = tmp_path / "report.json"
    payload = build_report_json_payload(
        run_id="rf08-md",
        dataset_hash="hash-md",
        summary={"overall_status": "ERROR", "tests_total": 1, "tests_error": 1},
        test_runs=[
            {
                "test_id": "TST-C",
                "version": "1.0.0",
                "status": "ERROR",
                "duration_ms": 3,
                "error_summary": "ValueError: invalid data",
            }
        ],
    )
    write_report_json(output_path=report_json_path, payload=payload)
    report_md_path = write_report_markdown_from_report_json(report_json_path=report_json_path)
    content = report_md_path.read_text(encoding="utf-8")
    assert "## Errores" in content
    assert "TST-C" in content
    assert "ValueError: invalid data" in content


def test_write_report_markdown_from_report_json_includes_test_cards_section(tmp_path: Path) -> None:
    report_json_path = tmp_path / "report_cards.json"
    payload = build_report_json_payload(
        run_id="rf13-04-md",
        dataset_hash="hash-cards",
        metadata_extra={
            "test_report_cards": [
                {
                    "test_id": "TST-ROUND-DOLLAR-PAYMENTS",
                    "name": "Round-dollar payments by vendor",
                    "fraud_type": "suspicious_payment_pattern",
                    "process_step": "invoice_posting",
                    "description": "Detecta pagos con importes redondos.",
                    "acfe_reference": "round_dollar_payments",
                    "expected_output_notes": "Marca pagos con importe entero.",
                    "sample_artifact": "run_results/x/tests_outputs/TST-ROUND-DOLLAR-PAYMENTS/sample_top20.json",
                    "evidence_columns": ["Kreditor", "Belegnummer", "Betrag"],
                }
            ]
        },
    )
    write_report_json(output_path=report_json_path, payload=payload)
    report_md_path = write_report_markdown_from_report_json(report_json_path=report_json_path)
    content = report_md_path.read_text(encoding="utf-8")
    assert "## Explicación mínima por test" in content
    assert "TST-ROUND-DOLLAR-PAYMENTS" in content
    assert "round_dollar_payments" in content


def test_write_report_markdown_from_report_json_includes_red_flags_section(tmp_path: Path) -> None:
    report_json_path = tmp_path / "report_red_flags.json"
    payload = build_report_json_payload(
        run_id="rf13-17-md",
        dataset_hash="hash-red-flags",
        metadata_extra={
            "red_flags_activated": [
                {
                    "test_id": "TST-SPLIT-PAYMENTS-NEAR-LIMIT",
                    "red_flag_id": "RF-P2P-005",
                    "finding_count": 3,
                    "evidence_columns": ["Kreditor", "Belegnummer", "Position", "Betrag"],
                    "explanation": "Detecta facturas con líneas fraccionadas para superar umbral de autorización agregado.",
                    "sample_artifact": "run_results/x/tests_outputs/TST-SPLIT-PAYMENTS-NEAR-LIMIT/sample_top20.json",
                }
            ]
        },
    )
    write_report_json(output_path=report_json_path, payload=payload)
    report_md_path = write_report_markdown_from_report_json(report_json_path=report_json_path)
    content = report_md_path.read_text(encoding="utf-8")
    assert "## Red Flags activadas" in content
    assert "RF-P2P-005" in content
    assert "TST-SPLIT-PAYMENTS-NEAR-LIMIT" in content


def test_write_report_markdown_from_report_json_red_flags_section_empty_when_no_findings(
    tmp_path: Path,
) -> None:
    report_json_path = tmp_path / "report_red_flags_empty.json"
    payload = build_report_json_payload(
        run_id="rf13-17-empty",
        dataset_hash="hash-empty",
        metadata_extra={"red_flags_activated": []},
    )
    write_report_json(output_path=report_json_path, payload=payload)
    report_md_path = write_report_markdown_from_report_json(report_json_path=report_json_path)
    content = report_md_path.read_text(encoding="utf-8")
    assert "## Red Flags activadas" in content
    assert "Sin red flags activadas en este run." in content


def test_write_report_markdown_from_report_json_includes_explanation_links(tmp_path: Path) -> None:
    report_json_path = tmp_path / "report_explanations.json"
    payload = build_report_json_payload(
        run_id="rf15-06-md",
        dataset_hash="hash-explanations",
        artifact_paths={
            "explanations_json": "run_results/rf15-06-md/graph/explanations.json",
            "explanations_md": "run_results/rf15-06-md/graph/explanations.md",
        },
    )
    write_report_json(output_path=report_json_path, payload=payload)
    report_md_path = write_report_markdown_from_report_json(report_json_path=report_json_path)
    content = report_md_path.read_text(encoding="utf-8")
    assert "## Explicaciones del agente" in content
    assert "explanations_json" in content
    assert "explanations.md" in content


def test_write_report_markdown_from_report_json_explanations_section_empty_when_missing_links(
    tmp_path: Path,
) -> None:
    report_json_path = tmp_path / "report_explanations_empty.json"
    payload = build_report_json_payload(
        run_id="rf15-06-md-empty",
        dataset_hash="hash-explanations-empty",
    )
    write_report_json(output_path=report_json_path, payload=payload)
    report_md_path = write_report_markdown_from_report_json(report_json_path=report_json_path)
    content = report_md_path.read_text(encoding="utf-8")
    assert "## Explicaciones del agente" in content
    assert "Sin explicaciones persistidas en este run." in content


def test_render_report_markdown_to_html_creates_html(tmp_path: Path) -> None:
    report_md_path = tmp_path / "report.md"
    report_md_path.write_text("# Report\n\n## Resumen\n\n- ok\n", encoding="utf-8")
    report_html_path = render_report_markdown_to_html(report_md_path=report_md_path)
    html_content = report_html_path.read_text(encoding="utf-8")
    assert report_html_path.suffix == ".html"
    assert "<html" in html_content.lower()
    assert "report" in html_content.lower()


def test_validate_report_json_file_artifact_links_detects_missing(tmp_path: Path) -> None:
    report_json_path = tmp_path / "report.json"
    payload = build_report_json_payload(
        run_id="rf08-links",
        dataset_hash="hash-links",
        artifact_paths={
            "existing": str(tmp_path / "ok.txt"),
            "missing": str(tmp_path / "missing.txt"),
        },
    )
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
    write_report_json(output_path=report_json_path, payload=payload)
    missing = validate_report_json_file_artifact_links(
        report_json_path=report_json_path,
        base_path=".",
    )
    missing_keys = {row["artifact_key"] for row in missing}
    assert "missing" in missing_keys


def test_validate_report_json_file_artifact_links_ok_when_all_exist(tmp_path: Path) -> None:
    run_id = "rf08-links-ok"
    run_dir = tmp_path / "run_results" / run_id
    (run_dir / "tests_outputs" / "TST-A").mkdir(parents=True, exist_ok=True)
    for path in [
        run_dir / "report.json",
        run_dir / "report.md",
        run_dir / "report.html",
        run_dir / "ranking.json",
        run_dir / "ranking.parquet",
        run_dir / "test_runs.json",
        run_dir / "data_validation_report.json",
        run_dir / "tests_outputs" / "TST-A" / "findings.jsonl",
        run_dir / "tests_outputs" / "TST-A" / "findings.parquet",
        run_dir / "tests_outputs" / "TST-A" / "sample_top20.json",
        tmp_path / "schema_summary.json",
        tmp_path / "data_dictionary.json",
        tmp_path / "data_dictionary.md",
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    payload = build_report_json_payload(
        run_id=run_id,
        dataset_hash="hash-ok",
        test_runs=[{"test_id": "TST-A", "version": "1.0.0", "status": "OK", "duration_ms": 1, "error_summary": ""}],
    )
    report_json_path = run_dir / "report_full.json"
    write_report_json(output_path=report_json_path, payload=payload)

    missing = validate_report_json_file_artifact_links(
        report_json_path=report_json_path,
        base_path=tmp_path,
    )
    assert missing == []
