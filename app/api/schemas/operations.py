from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import Field

from .common import APIModel


OperationKind = Literal["dataset_upload", "drilldown"]
OperationStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]


class OperationStatusResponse(APIModel):
    job_id: str
    kind: OperationKind
    status: OperationStatus
    stage: str
    message: str
    progress: int = Field(ge=0, le=100)
    created_at_utc: datetime
    updated_at_utc: datetime
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
