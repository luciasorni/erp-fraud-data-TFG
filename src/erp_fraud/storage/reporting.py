"""Utilidades de reporte Markdown/HTML para resultados del pipeline."""

from __future__ import annotations

import json
import html
from pathlib import Path
from typing import Any


DATA_VALIDATION_SECTION_START = "<!-- DATA_VALIDATION_SECTION_START -->"
DATA_VALIDATION_SECTION_END = "<!-- DATA_VALIDATION_SECTION_END -->"
DRILLDOWN_SECTION_START = "<!-- DRILLDOWN_SECTION_START -->"
DRILLDOWN_SECTION_END = "<!-- DRILLDOWN_SECTION_END -->"


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def build_report_markdown_template(
    *,
    run_id: str = "",
    dataset_hash: str = "",
) -> str:
    """Plantilla base de report.md con secciones fijas (RF08-02)."""
    resolved_run_id = run_id.strip() if isinstance(run_id, str) else ""
    resolved_dataset_hash = dataset_hash.strip() if isinstance(dataset_hash, str) else ""

    lines = [
        "# Report",
        "",
        "## Resumen",
        "",
        f"- `run_id`: `{resolved_run_id}`",
        f"- `dataset_hash`: `{resolved_dataset_hash}`",
        "- `overall_status`: `PENDING`",
        "- `generated_at_utc`: `PENDING`",
        "",
        "## Estado de tests",
        "",
        "| test_id | version | status | duration_ms | error_summary |",
        "|---|---:|---:|---:|---|",
        "| PENDING | PENDING | PENDING | 0 | |",
        "",
        "## Top-k sospechosos",
        "",
        "| rank | entity_key | score_total | tests_triggered |",
        "|---:|---|---:|---|",
        "| 1 | PENDING | 0.0 | PENDING |",
        "",
        "## Anexos por test",
        "",
        "- `tests_outputs/<test_id>/findings.jsonl`",
        "- `tests_outputs/<test_id>/sample_top20.json`",
        "",
        "## Errores",
        "",
        "- Sin errores registrados.",
        "",
    ]
    return "\n".join(lines)


def write_report_markdown_template(
    *,
    report_md_path: str | Path,
    run_id: str = "",
    dataset_hash: str = "",
    overwrite: bool = False,
) -> Path:
    """Escribe plantilla base de report.md en disco (RF08-02)."""
    report_path = Path(report_md_path)
    if report_path.exists() and not overwrite:
        return report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    content = build_report_markdown_template(run_id=run_id, dataset_hash=dataset_hash)
    report_path.write_text(content, encoding="utf-8")
    return report_path


def build_report_markdown_from_report_json_payload(
    *,
    report_payload: dict[str, Any],
) -> str:
    """Genera Markdown completo a partir de `report.json` (RF08-03)."""
    metadata = report_payload.get("metadata", {}) if isinstance(report_payload, dict) else {}
    summary = report_payload.get("summary", {}) if isinstance(report_payload, dict) else {}
    ranking = report_payload.get("ranking", {}) if isinstance(report_payload, dict) else {}
    test_runs = report_payload.get("test_runs", []) if isinstance(report_payload, dict) else []
    artifact_paths = report_payload.get("artifact_paths", {}) if isinstance(report_payload, dict) else {}
    errors = report_payload.get("errors", []) if isinstance(report_payload, dict) else []

    run_id = str(metadata.get("run_id", ""))
    dataset_hash = str(metadata.get("dataset_hash", ""))
    metadata_extra = metadata.get("metadata_extra", {}) if isinstance(metadata, dict) else {}
    if not isinstance(metadata_extra, dict):
        metadata_extra = {}
    generated_at_utc = str(report_payload.get("generated_at_utc", ""))
    overall_status = str(summary.get("overall_status", "UNKNOWN"))

    lines = [
        "# Report",
        "",
        "## Resumen",
        "",
        f"- `run_id`: `{_md(run_id)}`",
        f"- `dataset_hash`: `{_md(dataset_hash)}`",
        f"- `overall_status`: `{_md(overall_status)}`",
        f"- `generated_at_utc`: `{_md(generated_at_utc)}`",
        f"- `tests_total`: `{int(summary.get('tests_total', 0) or 0)}`",
        f"- `tests_ok`: `{int(summary.get('tests_ok', 0) or 0)}`",
        f"- `tests_error`: `{int(summary.get('tests_error', 0) or 0)}`",
        f"- `tests_timeout`: `{int(summary.get('tests_timeout', 0) or 0)}`",
        f"- `findings_total`: `{int(summary.get('findings_total', 0) or 0)}`",
        "",
        "## Estado de tests",
        "",
        "| test_id | version | status | duration_ms | error_summary |",
        "|---|---:|---:|---:|---|",
    ]

    if isinstance(test_runs, list) and test_runs:
        sorted_test_runs = sorted(
            [row for row in test_runs if isinstance(row, dict)],
            key=lambda row: str(row.get("test_id", "")),
        )
        for row in sorted_test_runs:
            lines.append(
                "| "
                + f"{_md(row.get('test_id', ''))} | "
                + f"{_md(row.get('version', ''))} | "
                + f"{_md(row.get('status', ''))} | "
                + f"{int(row.get('duration_ms', 0) or 0)} | "
                + f"{_md(row.get('error_summary', ''))} |"
            )
    else:
        lines.append("| - | - | - | 0 | |")

    top_k = ranking.get("top_k") if isinstance(ranking, dict) else None
    ranking_rows = ranking.get("rows", []) if isinstance(ranking, dict) else []
    if not isinstance(ranking_rows, list):
        ranking_rows = []

    lines.extend(
        [
            "",
            "## Top-k sospechosos",
            "",
            f"- `top_k`: `{_md(top_k)}`",
            f"- `row_count`: `{len(ranking_rows)}`",
            "",
            "| rank | entity_key | score_total | tests_triggered |",
            "|---:|---|---:|---|",
        ]
    )

    if ranking_rows:
        for idx, row in enumerate(ranking_rows, start=1):
            if not isinstance(row, dict):
                continue
            tests_triggered = row.get("tests_triggered", [])
            if isinstance(tests_triggered, list):
                tests_text = ", ".join(str(item) for item in tests_triggered)
            else:
                tests_text = str(tests_triggered)
            lines.append(
                f"| {idx} | {_md(row.get('entity_key', ''))} | "
                f"{_md(row.get('score_total', 0.0))} | {_md(tests_text)} |"
            )
    else:
        lines.append("| 1 | - | 0.0 | - |")

    lines.extend(["", "## Anexos por test", ""])
    if isinstance(artifact_paths, dict) and artifact_paths:
        for key in sorted(artifact_paths.keys()):
            path = artifact_paths.get(key)
            lines.append(f"- `{_md(key)}`: `{_md(path)}`")
    else:
        lines.append("- Sin anexos registrados.")

    lines.extend(["", "## Explicación mínima por test", ""])
    test_cards = metadata_extra.get("test_report_cards", [])
    if isinstance(test_cards, list) and test_cards:
        for card in sorted(
            [row for row in test_cards if isinstance(row, dict)],
            key=lambda row: str(row.get("test_id", "")),
        ):
            lines.extend(
                [
                    f"- `test_id`: `{_md(card.get('test_id', ''))}`",
                    f"  - `name`: `{_md(card.get('name', ''))}`",
                    f"  - `fraud_type`: `{_md(card.get('fraud_type', ''))}`",
                    f"  - `process_step`: `{_md(card.get('process_step', ''))}`",
                    f"  - `acfe_reference`: `{_md(card.get('acfe_reference', ''))}`",
                    f"  - `description`: {_md(card.get('description', ''))}",
                    f"  - `expected_output_notes`: {_md(card.get('expected_output_notes', ''))}",
                    f"  - `sample_artifact`: `{_md(card.get('sample_artifact', ''))}`",
                ]
            )
            evidence = card.get("evidence_columns", [])
            if isinstance(evidence, list) and evidence:
                lines.append(f"  - `evidence_columns`: `{_md(', '.join(str(item) for item in evidence))}`")
            else:
                lines.append("  - `evidence_columns`: ``")
    else:
        lines.append("- Sin tarjetas de test registradas.")

    lines.extend(["", "## Errores", ""])
    failed_runs: list[dict[str, Any]] = []
    if isinstance(test_runs, list):
        for row in test_runs:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status", "")).upper()
            if status in {"ERROR", "TIMEOUT"}:
                failed_runs.append(row)

    if failed_runs:
        lines.extend(
            [
                "",
                "| test_id | status | error_summary |",
                "|---|---|---|",
            ]
        )
        for row in sorted(failed_runs, key=lambda item: str(item.get("test_id", ""))):
            lines.append(
                "| "
                + f"{_md(row.get('test_id', ''))} | "
                + f"{_md(row.get('status', ''))} | "
                + f"{_md(row.get('error_summary', ''))} |"
            )
        lines.append("")

    if isinstance(errors, list) and errors:
        for item in errors:
            if not isinstance(item, dict):
                continue
            scope = item.get("scope", "")
            code = item.get("code", "")
            message = item.get("message", "")
            lines.append(f"- `[{_md(scope)}:{_md(code)}]` {_md(message)}")
    else:
        lines.append("- Sin errores registrados.")

    lines.append("")
    return "\n".join(lines)


def write_report_markdown_from_report_json(
    *,
    report_json_path: str | Path,
    report_md_path: str | Path | None = None,
) -> Path:
    """Lee `report.json` y escribe `report.md` equivalente (RF08-03)."""
    json_path = Path(report_json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"No existe report.json: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("report.json debe contener un objeto raíz")

    if report_md_path is None:
        output_path = json_path.with_suffix(".md")
    else:
        output_path = Path(report_md_path)

    markdown = build_report_markdown_from_report_json_payload(report_payload=payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def _simple_markdown_to_html(markdown_text: str) -> str:
    escaped = html.escape(markdown_text)
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Report</title>\n"
        "  <style>\n"
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem auto; max-width: 1100px; padding: 0 1rem; }\n"
        "    pre { white-space: pre-wrap; word-wrap: break-word; background: #f7f7f7; border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <pre>\n"
        f"{escaped}\n"
        "  </pre>\n"
        "</body>\n"
        "</html>\n"
    )


def render_report_markdown_to_html(
    *,
    report_md_path: str | Path,
    report_html_path: str | Path | None = None,
) -> Path:
    """Render opcional de report.md -> report.html (RF08-04)."""
    md_path = Path(report_md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"No existe report.md: {md_path}")

    markdown_text = md_path.read_text(encoding="utf-8")

    html_content: str
    try:
        import markdown as md_lib  # type: ignore

        rendered = md_lib.markdown(
            markdown_text,
            extensions=["tables", "fenced_code"],
        )
        html_content = (
            "<!doctype html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
            "  <title>Report</title>\n"
            "  <style>\n"
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem auto; max-width: 1100px; padding: 0 1rem; }\n"
            "    table { border-collapse: collapse; width: 100%; }\n"
            "    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n"
            "    th { background: #f7f7f7; }\n"
            "    code { background: #f7f7f7; padding: 2px 4px; border-radius: 4px; }\n"
            "    pre code { display: block; padding: 12px; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            f"{rendered}\n"
            "</body>\n"
            "</html>\n"
        )
    except Exception:
        html_content = _simple_markdown_to_html(markdown_text)

    if report_html_path is None:
        output_path = md_path.with_suffix(".html")
    else:
        output_path = Path(report_html_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def _build_data_validation_markdown_section(
    *,
    data_validation_report_path: Path,
    summary: dict,
) -> str:
    overall_status = summary.get("overall_status", "UNKNOWN")
    critical = summary.get("critical_errors_count", 0)
    warnings = summary.get("warning_findings_count", 0)
    checks_total = summary.get("checks_total", 0)

    rel_link = data_validation_report_path.as_posix()
    lines = [
        DATA_VALIDATION_SECTION_START,
        "## Data Validation",
        "",
        f"- `overall_status`: **{overall_status}**",
        f"- `critical_errors_count`: `{critical}`",
        f"- `warning_findings_count`: `{warnings}`",
        f"- `checks_total`: `{checks_total}`",
        "",
        f"- `data_validation_report`: [{rel_link}]({rel_link})",
        DATA_VALIDATION_SECTION_END,
        "",
    ]
    return "\n".join(lines)


def _build_drilldown_markdown_section(
    *,
    run_id: str,
) -> str:
    lines = [
        DRILLDOWN_SECTION_START,
        "## Drilldown",
        "",
        "Para inspeccionar filas origen de un hallazgo, usa el comando seguro de drilldown:",
        "",
        "```bash",
        "python3 -m src.erp_fraud.cli.main drilldown \\",
        f"  --run-id {run_id} \\",
        "  --test-id <TEST_ID> \\",
        "  --entity-key '<ENTITY_KEY>' \\",
        "  --save-default",
        "```",
        "",
        "Opcional:",
        "- `--limit-rows 200`",
        "- `--order-direction ASC|DESC`",
        "- `--transaktionsart <valor>` (filtro permitido)",
        "",
        "Salida por defecto:",
        f"- `run_results/{run_id}/drilldown_<test_id>.json`",
        DRILLDOWN_SECTION_END,
        "",
    ]
    return "\n".join(lines)


def _upsert_section(
    *,
    current: str,
    section: str,
    start_marker: str,
    end_marker: str,
) -> str:
    if start_marker in current and end_marker in current:
        start_idx = current.index(start_marker)
        end_idx = current.index(end_marker) + len(end_marker)
        return current[:start_idx] + section + current[end_idx:]
    if not current.endswith("\n"):
        current += "\n"
    return current + "\n" + section


def write_or_update_report_markdown_with_data_validation(
    *,
    report_md_path: str | Path,
    data_validation_report_path: str | Path,
) -> Path:
    """Escribe/actualiza sección de validación técnica en `report.md`."""
    report_path = Path(report_md_path)
    validation_path = Path(data_validation_report_path)
    if not validation_path.exists():
        raise FileNotFoundError(f"No existe data_validation_report: {validation_path}")

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    summary = validation.get("summary", {})
    section = _build_data_validation_markdown_section(
        data_validation_report_path=validation_path,
        summary=summary,
    )

    if report_path.exists():
        current = report_path.read_text(encoding="utf-8")
    else:
        current = "# Report\n\n"

    updated = _upsert_section(
        current=current,
        section=section,
        start_marker=DATA_VALIDATION_SECTION_START,
        end_marker=DATA_VALIDATION_SECTION_END,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(updated, encoding="utf-8")
    return report_path


def write_or_update_report_markdown_with_drilldown_instructions(
    *,
    report_md_path: str | Path,
    run_id: str,
) -> Path:
    """Escribe/actualiza sección de instrucciones de drilldown en `report.md`."""
    if not run_id or not run_id.strip():
        raise ValueError("run_id debe ser string no vacío")

    report_path = Path(report_md_path)
    section = _build_drilldown_markdown_section(run_id=run_id.strip())

    if report_path.exists():
        current = report_path.read_text(encoding="utf-8")
    else:
        current = "# Report\n\n"

    updated = _upsert_section(
        current=current,
        section=section,
        start_marker=DRILLDOWN_SECTION_START,
        end_marker=DRILLDOWN_SECTION_END,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(updated, encoding="utf-8")
    return report_path
