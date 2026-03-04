"""Integración de validación técnica en pipeline (RF02b-08)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .data_validation_report import build_data_validation_report, write_data_validation_report_json
from .data_validation_requirements import extract_required_columns_from_testspecs
from .duckdb_store import DEFAULT_DUCKDB_PATH


@dataclass(frozen=True)
class TechnicalValidationOutcome:
    """Resultado de validación técnica previa a ejecución de tests."""

    status: str
    should_block_run: bool
    critical_errors_count: int
    warning_findings_count: int
    report_path: str
    required_tables_count: int
    required_columns_count: int


def run_technical_validation_before_tests(
    *,
    test_specs: list[dict],
    report_output_path: str | Path,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    schema_name: str = "main",
) -> TechnicalValidationOutcome:
    """Ejecuta validación técnica y bloquea solo cuando hay críticos."""
    required_by_table = extract_required_columns_from_testspecs(test_specs)
    required_columns_count = sum(len(cols) for cols in required_by_table.values())

    report = build_data_validation_report(
        required_by_table,
        db_path=db_path,
        schema_name=schema_name,
    )
    report_path = write_data_validation_report_json(
        report_output_path,
        required_columns_by_table=required_by_table,
        db_path=db_path,
        schema_name=schema_name,
    )

    summary = report.get("summary", {})
    critical_errors_count = int(summary.get("critical_errors_count", 0))
    warning_findings_count = int(summary.get("warning_findings_count", 0))
    status = str(summary.get("overall_status", "OK"))
    should_block_run = critical_errors_count > 0

    return TechnicalValidationOutcome(
        status=status,
        should_block_run=should_block_run,
        critical_errors_count=critical_errors_count,
        warning_findings_count=warning_findings_count,
        report_path=str(report_path),
        required_tables_count=len(required_by_table),
        required_columns_count=required_columns_count,
    )
