from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import Field

from .common import APIModel
from .operations import OperationStatusResponse


DrilldownAction = Literal["finding_rows"]
DrilldownOrder = Literal["ASC", "DESC"]


class DrilldownRequest(APIModel):
    action: DrilldownAction = "finding_rows"
    test_id: str
    keys: Dict[str, str]
    extra_filters: Dict[str, str] = Field(default_factory=dict)
    limit_rows: int = Field(default=50, ge=1, le=200)
    order_direction: DrilldownOrder = "ASC"


class DrilldownResponse(APIModel):
    run_id: str
    action: DrilldownAction
    test_id: str
    query_id: str
    row_count: int
    rows: List[Dict[str, Any]]
    allowed_actions: List[str]


class DrilldownJobResponse(OperationStatusResponse):
    pass
