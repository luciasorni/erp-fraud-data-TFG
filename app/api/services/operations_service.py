from __future__ import annotations

from datetime import datetime, timezone
import threading
import uuid
from typing import Any, Callable, Dict, Optional

from ..schemas.operations import OperationStatusResponse


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}


def create_job(*, kind: str, stage: str, message: str) -> OperationStatusResponse:
    job_id = str(uuid.uuid4())
    now = _utc_now()
    payload = {
        "job_id": job_id,
        "kind": kind,
        "status": "QUEUED",
        "stage": stage,
        "message": message,
        "progress": 0,
        "created_at_utc": now,
        "updated_at_utc": now,
        "result": None,
        "error": None,
    }
    with _LOCK:
        _JOBS[job_id] = payload
    return OperationStatusResponse(**payload)


def get_job(*, job_id: str) -> Optional[OperationStatusResponse]:
    with _LOCK:
        payload = _JOBS.get(job_id)
        if not payload:
            return None
        return OperationStatusResponse(**payload)


def update_job(
    *,
    job_id: str,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    message: Optional[str] = None,
    progress: Optional[int] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> OperationStatusResponse:
    with _LOCK:
        payload = dict(_JOBS[job_id])
        if status is not None:
            payload["status"] = status
        if stage is not None:
            payload["stage"] = stage
        if message is not None:
            payload["message"] = message
        if progress is not None:
            payload["progress"] = max(0, min(100, int(progress)))
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error
        payload["updated_at_utc"] = _utc_now()
        _JOBS[job_id] = payload
        return OperationStatusResponse(**payload)


def run_job_in_thread(
    *,
    job_id: str,
    target: Callable[[], Dict[str, Any]],
) -> None:
    def _runner() -> None:
        update_job(job_id=job_id, status="RUNNING", progress=5)
        try:
            result = target()
            update_job(
                job_id=job_id,
                status="SUCCEEDED",
                stage="completed",
                message="Operación completada correctamente.",
                progress=100,
                result=result,
                error=None,
            )
        except Exception as exc:
            update_job(
                job_id=job_id,
                status="FAILED",
                stage="failed",
                message="La operación terminó con error.",
                progress=100,
                error=f"{type(exc).__name__}: {exc}",
            )

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()

