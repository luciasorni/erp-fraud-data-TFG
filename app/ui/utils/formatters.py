from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from .constants import SCOPE_LABELS, STATUS_LABELS


def format_datetime(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
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

