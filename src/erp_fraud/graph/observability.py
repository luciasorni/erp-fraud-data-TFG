"""Observabilidad y taxonomía de errores del grafo (RF14b-P03)."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any
from ..config.env import parse_bool_env


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


def _env_bool(name: str) -> bool:
    return parse_bool_env(os.getenv(name, ""), default=False)


def get_langsmith_snapshot() -> dict[str, Any]:
    project = str(os.getenv("LANGSMITH_PROJECT", "")).strip()
    endpoint = str(os.getenv("LANGSMITH_ENDPOINT", "")).strip()
    api_key_present = bool(str(os.getenv("LANGSMITH_API_KEY", "")).strip())
    tracing_enabled = _env_bool("LANGSMITH_TRACING") or _env_bool("LANGCHAIN_TRACING_V2")
    return {
        "tracing_enabled": tracing_enabled,
        "api_key_present": api_key_present,
        "project": project,
        "endpoint": endpoint,
        "configured": bool(tracing_enabled and api_key_present and project),
    }


def summarize_graph_state(state: Any) -> dict[str, Any]:
    run_metadata = getattr(state, "run_metadata", {})
    if not isinstance(run_metadata, dict):
        run_metadata = {}
    return {
        "run_id": str(getattr(state, "run_id", "")).strip(),
        "hypotheses_count": len(getattr(state, "hypotheses", []) or []),
        "selected_tests_count": len(getattr(state, "selected_tests", []) or []),
        "findings_count": len(getattr(state, "findings", []) or []),
        "test_runs_count": len(getattr(state, "test_runs", []) or []),
        "ranking_count": len(getattr(state, "ranking", []) or []),
        "fraud_type_predicho_count": len(getattr(state, "fraud_type_predicho", []) or []),
        "recomendaciones_count": len(getattr(state, "recomendaciones", []) or []),
        "explanations_count": len(getattr(state, "explanations", []) or []),
        "scores_count": len(getattr(state, "scores", []) or []),
        "graph_status": str(run_metadata.get("graph_status", "")).strip(),
    }


def append_trace_event(
    *,
    run_metadata: dict[str, Any],
    node_id: str,
    stage: str,
    attempt: int,
    duration_ms: int | None = None,
    status: str | None = None,
    input_summary: dict[str, Any] | None = None,
    output_summary: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    events = run_metadata.setdefault("node_trace_events", [])
    if not isinstance(events, list):
        return
    payload: dict[str, Any] = {
        "ts_utc": _utc_now_iso(),
        "node_id": str(node_id).strip(),
        "stage": str(stage).strip(),
        "attempt": int(attempt),
    }
    if duration_ms is not None:
        payload["duration_ms"] = int(duration_ms)
    if status:
        payload["status"] = str(status).strip()
    if input_summary is not None:
        payload["input_summary"] = input_summary
    if output_summary is not None:
        payload["output_summary"] = output_summary
    if error:
        payload["error"] = str(error)
    events.append(payload)
