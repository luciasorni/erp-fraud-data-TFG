from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .constants import DISPLAY_TIMEZONE, SCOPE_LABELS, STATUS_LABELS


def format_datetime(value: Optional[Any]) -> str:
    if not value:
        return "-"
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        dt = dt.astimezone(ZoneInfo(DISPLAY_TIMEZONE))
    except Exception:
        pass
    return dt.strftime("%d/%m/%Y %H:%M")


def format_scope(scope: Optional[str]) -> str:
    if not scope:
        return "-"
    return SCOPE_LABELS.get(scope, scope.upper())


def format_status(status: Optional[str]) -> str:
    if not status:
        return STATUS_LABELS["UNKNOWN"]
    return STATUS_LABELS.get(status, status.replace("_", " ").title())


def format_bool(value: Optional[bool]) -> str:
    if value is None:
        return "-"
    return "Sí" if value else "No"


def format_bytes(size_bytes: Optional[int]) -> str:
    if size_bytes is None:
        return "-"
    size = float(size_bytes)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{int(size_bytes)} B"


def coalesce_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return "-"


def normalize_structured_content(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): normalize_structured_content(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [normalize_structured_content(item) for item in value]
    if isinstance(value, list):
        return [normalize_structured_content(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text[:1] in {"{", "[", "("}:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, (dict, list, tuple)):
                    return normalize_structured_content(parsed)
            except Exception:
                pass
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, (dict, list, tuple)):
                    return normalize_structured_content(parsed)
            except Exception:
                pass
        return text
    return value


def presentable_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    custom = {
        "key_evidence": "Evidencia clave",
        "overall_assessment": "Valoración global",
        "risk_posture": "Postura de riesgo",
        "action": "Acción",
        "owner": "Responsable",
        "urgency": "Urgencia",
        "conclusion": "Conclusión",
        "evidence": "Evidencia",
        "severity": "Severidad",
        "procedure": "Procedimiento",
        "why": "Motivo",
        "rationale": "Justificación",
        "priority": "Prioridad",
        "expected_value": "Valor esperado",
        "recommended_tests": "Tests recomendados",
        "audit_procedures": "Procedimientos de auditoría",
    }
    if text in custom:
        return custom[text]
    return text.replace("_", " ").strip().capitalize()


def summarize_structured_content(value: Any) -> str:
    normalized = normalize_structured_content(value)
    if normalized is None:
        return "-"
    if isinstance(normalized, dict):
        parts = []
        for key, item in normalized.items():
            if isinstance(item, (dict, list)):
                continue
            text = str(item).strip()
            if text:
                parts.append(f"{presentable_label(key)}: {text}")
        if parts:
            return " · ".join(parts)
        return ", ".join(presentable_label(key) for key in normalized.keys()) or "-"
    if isinstance(normalized, list):
        scalar_items = [str(item).strip() for item in normalized if not isinstance(item, (dict, list)) and str(item).strip()]
        if scalar_items:
            return "; ".join(scalar_items)
        return f"{len(normalized)} elementos"
    return str(normalized).strip() or "-"
