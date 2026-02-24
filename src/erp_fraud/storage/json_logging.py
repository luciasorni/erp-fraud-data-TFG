"""Logging estructurado JSON (JSONL) para el pipeline de ingesta."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .paths import ruta_run


DEFAULT_INGEST_LOG_FILENAME = "ingest_logs.jsonl"


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Exception):
        return {"type": type(value).__name__, "message": str(value)}
    return value


class IngestJsonLogger:
    """Escribe eventos JSONL de una ejecución de ingesta."""

    def __init__(self, run_id: str, log_path: str | Path):
        if not run_id or not run_id.strip():
            raise ValueError("run_id debe ser un string no vacío")
        self.run_id = run_id.strip()
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_run(
        cls,
        run_id: str,
        *,
        filename: str = DEFAULT_INGEST_LOG_FILENAME,
    ) -> "IngestJsonLogger":
        return cls(run_id=run_id, log_path=ruta_run(run_id) / filename)

    def log_event(self, *, level: str, event: str, **fields: Any) -> dict[str, Any]:
        record = {
            "timestamp_utc": _timestamp_utc(),
            "level": level.upper(),
            "event": event,
            "run_id": self.run_id,
        }
        record.update({key: _json_safe(value) for key, value in fields.items()})
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def log_ingest_start(self, **fields: Any) -> dict[str, Any]:
        return self.log_event(level="INFO", event="ingest_start", **fields)

    def log_ingest_end(self, **fields: Any) -> dict[str, Any]:
        return self.log_event(level="INFO", event="ingest_end", **fields)

    def log_table_load(self, *, table_name: str, **fields: Any) -> dict[str, Any]:
        return self.log_event(
            level="INFO",
            event="table_load",
            table_name=table_name,
            **fields,
        )

    def log_warning(self, message: str, **fields: Any) -> dict[str, Any]:
        return self.log_event(level="WARNING", event="warning", message=message, **fields)

    def log_error(self, message: str, **fields: Any) -> dict[str, Any]:
        return self.log_event(level="ERROR", event="error", message=message, **fields)
