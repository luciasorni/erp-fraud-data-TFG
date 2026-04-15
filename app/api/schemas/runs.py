from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import Field

from .common import APIModel, CompositeRunRefs, CompositeTaskRefs


RunScope = Literal["p2p", "o2c", "both"]
GraphPipelineMode = Literal["graph"]
LLMMode = Literal["stub", "real"]


class RunCreateRequest(APIModel):
    dataset_id: str
    scope: RunScope
    pipeline_mode: GraphPipelineMode = "graph"
    llm_mode: LLMMode = "stub"
    kb_index_enabled: bool = False


class RunCreateResponse(APIModel):
    composite_run: bool
    submitted_at_utc: datetime
    pipeline_mode: GraphPipelineMode
    llm_mode: LLMMode
    kb_index_enabled: bool
    dataset_id: str
    scope: RunScope
    run_id: Optional[str] = None
    task_arn: Optional[str] = None
    run_ids: Optional[CompositeRunRefs] = None
    task_arns: Optional[CompositeTaskRefs] = None


class RunSummaryResponse(APIModel):
    run_id: str
    dataset_id: Optional[str] = None
    scope: Optional[Literal["p2p", "o2c"]] = None
    pipeline_mode: Optional[str] = None
    llm_mode: Optional[str] = None
    kb_index_enabled: Optional[bool] = None
    status: str
    graph_status: Optional[str] = None
    kb_index_status: Optional[str] = None
    process_family: Optional[str] = None
    task_arn: Optional[str] = None
    created_at_utc: Optional[datetime] = None
    updated_at_utc: Optional[datetime] = None


class RunDetailResponse(APIModel):
    run_id: str
    dataset_id: Optional[str] = None
    scope: Optional[Literal["p2p", "o2c"]] = None
    pipeline_mode: Optional[str] = None
    llm_mode: Optional[str] = None
    kb_index_enabled: Optional[bool] = None
    process_family: Optional[str] = None
    kb_index_status: Optional[str] = None
    status: str
    graph_status: Optional[str] = None
    task_arn: Optional[str] = None
    task_status: Optional[Dict[str, Any]] = None
    created_at_utc: Optional[datetime] = None
    updated_at_utc: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    artifact_keys: Dict[str, str] = Field(default_factory=dict)
