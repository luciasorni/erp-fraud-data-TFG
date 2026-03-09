"""Utilidades de reporte Markdown/HTML para resultados del pipeline."""

from __future__ import annotations

import json
from pathlib import Path


DATA_VALIDATION_SECTION_START = "<!-- DATA_VALIDATION_SECTION_START -->"
DATA_VALIDATION_SECTION_END = "<!-- DATA_VALIDATION_SECTION_END -->"
DRILLDOWN_SECTION_START = "<!-- DRILLDOWN_SECTION_START -->"
DRILLDOWN_SECTION_END = "<!-- DRILLDOWN_SECTION_END -->"


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
