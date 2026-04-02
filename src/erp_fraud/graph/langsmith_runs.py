"""Publicación opcional de trazas de run/nodos en LangSmith."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _app_base_url_from_endpoint(endpoint: str) -> str:
    raw = str(endpoint or "").strip().rstrip("/")
    if not raw:
        return ""
    return (
        raw.replace("https://eu.api.smith.langchain.com", "https://eu.smith.langchain.com")
        .replace("https://api.smith.langchain.com", "https://smith.langchain.com")
    )


def publish_langsmith_node_runs(*, state: Any) -> dict[str, Any]:
    run_metadata = getattr(state, "run_metadata", {})
    if not isinstance(run_metadata, dict):
        run_metadata = {}

    ls = run_metadata.get("langsmith", {})
    if not isinstance(ls, dict):
        ls = {}
    tracing_enabled = bool(ls.get("tracing_enabled", False))
    api_key_present = bool(ls.get("api_key_present", False))
    project = str(ls.get("project", "")).strip()
    endpoint = str(ls.get("endpoint", "")).strip()
    if not (tracing_enabled and api_key_present and project):
        return {
            "status": "SKIPPED",
            "reason": "langsmith_not_configured",
            "project": project,
            "runs_published": 0,
        }

    try:
        from langsmith import Client  # type: ignore
    except Exception as exc:
        return {
            "status": "SKIPPED",
            "reason": f"langsmith_sdk_not_installed:{type(exc).__name__}",
            "project": project,
            "runs_published": 0,
        }

    events = run_metadata.get("node_trace_events", [])
    if not isinstance(events, list):
        events = []
    if not events:
        return {
            "status": "SKIPPED",
            "reason": "no_node_trace_events",
            "project": project,
            "runs_published": 0,
        }

    try:
        client = Client()
        start_time = _now_utc()
        run_id = str(getattr(state, "run_id", "")).strip()
        dataset_hash = str(run_metadata.get("dataset_hash", "")).strip()
        tags = run_metadata.get("langsmith_tags", [])
        if not isinstance(tags, list):
            tags = []

        published = 0
        node_rows: list[dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            if str(event.get("stage", "")).strip().lower() != "end":
                continue
            node_id = str(event.get("node_id", "")).strip()
            if not node_id:
                continue
            duration_ms = int(event.get("duration_ms", 0) or 0)
            status = str(event.get("status", "")).strip().upper()
            error = str(event.get("error", "")).strip()
            row: dict[str, Any] = {
                "node_id": node_id,
                "status": status,
                "duration_ms": duration_ms,
            }
            if isinstance(event.get("output_summary"), dict):
                row["summary"] = event["output_summary"]
            if error:
                row["error"] = error
            node_rows.append(row)
            published += 1

        root_run_id = str(uuid4())
        created = client.create_run(
            id=root_run_id,
            name=f"erp_fraud_graph:{run_id or 'unknown'}",
            run_type="chain",
            project_name=project,
            inputs={"run_id": run_id, "dataset_hash": dataset_hash},
            outputs={
                "graph_status": str(run_metadata.get("graph_status", "")).strip() or "UNKNOWN",
                "nodes": node_rows,
                "nodes_count": len(node_rows),
            },
            start_time=start_time,
            end_time=_now_utc(),
            tags=[str(t).strip() for t in tags if str(t).strip()],
        )

        trace_link = ""
        # `create_run` devuelve dict-like con id en algunas versiones del SDK.
        run_ref = created if isinstance(created, dict) else {}
        created_id = str(run_ref.get("id", "")).strip()
        if not created_id:
            created_id = str(getattr(created, "id", "")).strip()
        if created_id:
            root_run_id = created_id
        if endpoint and project and root_run_id:
            app_base = _app_base_url_from_endpoint(endpoint)
            if app_base:
                trace_link = f"{app_base}/o/{project}/projects/p/{project}/r/{root_run_id}"
        return {
            "status": "OK",
            "reason": "",
            "project": project,
            "runs_published": 1,
            "node_events_count": published,
            "root_run_id": root_run_id,
            "trace_link": trace_link,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": f"{type(exc).__name__}: {exc}",
            "project": project,
            "runs_published": 0,
        }
