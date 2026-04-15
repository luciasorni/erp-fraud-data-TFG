from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorResponse(APIModel):
    code: str
    message: str
    detail: Optional[Dict[str, Any]] = None


class CountsSummary(APIModel):
    hypotheses: int = 0
    selected_tests: int = 0
    findings: int = 0
    scores: int = 0
    explanations: int = 0
    second_level_analysis: int = 0


class TaskLaunchRef(APIModel):
    run_id: str
    scope: str
    task_arn: str
    submitted_at_utc: datetime


class CompositeRunRefs(APIModel):
    p2p: Optional[str] = None
    o2c: Optional[str] = None


class CompositeTaskRefs(APIModel):
    p2p: Optional[str] = None
    o2c: Optional[str] = None


class UISectionItem(APIModel):
    id: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
