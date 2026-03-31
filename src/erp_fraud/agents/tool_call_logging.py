"""Logging estructurado para llamadas de tools (RF15b-08)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


def _timestamp_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_params_hash(params: dict[str, Any] | None) -> str:
    payload = params if isinstance(params, dict) else {}
    encoded = _stable_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ToolCallLogger:
    """Escritor JSONL para trazas de llamadas a tools."""

    def __init__(self, log_path: str | Path) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_tool_call(
        self,
        *,
        tool_id: str,
        agent_id: str,
        params: dict[str, Any] | None = None,
        status: str,
        duration_ms: int,
        node_id: str | None = None,
        error_summary: str | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "timestamp_utc": _timestamp_utc_iso(),
            "event": "tool_call",
            "tool_id": str(tool_id),
            "agent_id": str(agent_id),
            "params_hash": build_params_hash(params),
            "duration_ms": int(duration_ms),
            "status": str(status),
        }
        if node_id:
            record["node_id"] = str(node_id)
        if error_summary:
            record["error_summary"] = str(error_summary)

        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record
