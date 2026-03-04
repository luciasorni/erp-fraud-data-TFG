"""Política de severidades para validación técnica de dataset (RF02b)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["critical", "warning"]


@dataclass(frozen=True)
class ValidationRule:
    """Regla de severidad por tipo de hallazgo técnico."""

    check_name: str
    severity: Severity
    rationale: str


VALIDATION_SEVERITY_POLICY: tuple[ValidationRule, ...] = (
    ValidationRule(
        check_name="missing_required_columns",
        severity="critical",
        rationale="Sin columnas requeridas el test no puede ejecutarse de forma válida.",
    ),
    ValidationRule(
        check_name="type_parse_errors_dates",
        severity="critical",
        rationale="Errores de parseo de fechas en campos requeridos invalidan reglas temporales.",
    ),
    ValidationRule(
        check_name="type_parse_errors_amounts",
        severity="critical",
        rationale="Errores de parseo de importes en campos requeridos invalidan controles monetarios.",
    ),
    ValidationRule(
        check_name="null_percentage_required_columns",
        severity="warning",
        rationale="Nulos altos degradan calidad, pero no bloquean la ejecución por sí solos.",
    ),
    ValidationRule(
        check_name="basic_ranges_dates",
        severity="warning",
        rationale="Rangos atípicos de fechas son señal de calidad/anomalía, no fallo estructural.",
    ),
    ValidationRule(
        check_name="basic_ranges_amounts",
        severity="warning",
        rationale="Rangos extremos o negativos pueden ser anómalos, pero requieren análisis posterior.",
    ),
)


def get_validation_severity(check_name: str) -> Severity:
    """Devuelve severidad de un check; por defecto, `warning`."""
    for rule in VALIDATION_SEVERITY_POLICY:
        if rule.check_name == check_name:
            return rule.severity
    return "warning"


def is_critical_check(check_name: str) -> bool:
    """Indica si un check está catalogado como crítico."""
    return get_validation_severity(check_name) == "critical"


def get_validation_policy_dict() -> dict[str, dict[str, str]]:
    """Versión serializable de la política para reportes/documentación."""
    return {
        rule.check_name: {
            "severity": rule.severity,
            "rationale": rule.rationale,
        }
        for rule in VALIDATION_SEVERITY_POLICY
    }
