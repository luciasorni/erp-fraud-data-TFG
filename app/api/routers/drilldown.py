from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.drilldown import DrilldownRequest, DrilldownResponse
from ..services.aws_service import load_aws_api_settings
from ..services.drilldown_service import execute_drilldown


router = APIRouter()


@router.post("/runs/{run_id}/drilldown", response_model=DrilldownResponse)
def post_run_drilldown(run_id: str, payload: DrilldownRequest) -> DrilldownResponse:
    try:
        return execute_drilldown(run_id=run_id, payload=payload, settings=load_aws_api_settings())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

