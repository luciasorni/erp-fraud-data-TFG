"""Observabilidad y taxonomía de errores del grafo (RF14b-P03)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def classify_error_code(error_text: str) -> str:
    text = str(error_text or "").strip().upper()
    if "TIMEOUT" in text:
        return "TIMEOUT"
    if "TOOLPOLICYDENIEDERROR" in text or "POLICY" in text or "DENIED" in text:
        return "TOOL_DENIED"
    if "VALIDATION" in text or "SCHEMA" in text or "MISSING_FIELD" in text:
        return "VALIDATION_ERROR"
    if "FILE NOT FOUND" in text or "NO SUCH FILE" in text or "FILENOTFOUNDERROR" in text:
        return "IO_ERROR"
    if "VALUEERROR" in text or "TYPEERROR" in text:
        return "RUNTIME_ERROR"
    return "UNKNOWN_ERROR"


def append_error_event(
    *,
    run_metadata: dict[str, Any],
    node_id: str,
    status: str,
    error: str,
    attempt: int | None = None,
    phase: str = "graph",
) -> None:
    code = classify_error_code(error)
    errors = run_metadata.setdefault("errors", [])
    if isinstance(errors, list):
        payload: dict[str, Any] = {
            "ts_utc": _utc_now_iso(),
            "phase": phase,
            "node_id": node_id,
            "status": status,
            "code": code,
            "error": str(error),
        }
        if attempt is not None:
            payload["attempt"] = int(attempt)
        errors.append(payload)

    counts = run_metadata.setdefault("error_counts_by_code", {})
    if isinstance(counts, dict):
        counts[code] = int(counts.get(code, 0) or 0) + 1
