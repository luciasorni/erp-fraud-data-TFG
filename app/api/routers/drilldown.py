from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.drilldown import DrilldownJobResponse, DrilldownRequest, DrilldownResponse
from ..services.aws_service import load_aws_api_settings
from ..services.drilldown_service import execute_drilldown
from ..services.operations_service import create_job, get_job, run_job_in_thread, update_job


router = APIRouter()


@router.post("/runs/{run_id}/drilldown", response_model=DrilldownResponse)
def post_run_drilldown(run_id: str, payload: DrilldownRequest) -> DrilldownResponse:
    try:
        return execute_drilldown(run_id=run_id, payload=payload, settings=load_aws_api_settings())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/drilldown-jobs", response_model=DrilldownJobResponse, status_code=202)
def post_run_drilldown_job(run_id: str, payload: DrilldownRequest) -> DrilldownJobResponse:
    settings = load_aws_api_settings()
    job = create_job(kind="drilldown", stage="received", message="Solicitud de drilldown recibida.")

    def _status_callback(*, stage: str, message: str, progress: int) -> None:
        update_job(job_id=job.job_id, status="RUNNING", stage=stage, message=message, progress=progress)

    def _target() -> dict:
        response = execute_drilldown(
            run_id=run_id,
            payload=payload,
            settings=settings,
            status_callback=_status_callback,
        )
        return response.model_dump(mode="json")

    run_job_in_thread(job_id=job.job_id, target=_target)
    return DrilldownJobResponse(**job.model_dump())


@router.get("/runs/{run_id}/drilldown-jobs/{job_id}", response_model=DrilldownJobResponse)
def get_run_drilldown_job(run_id: str, job_id: str) -> DrilldownJobResponse:
    _ = run_id
    payload = get_job(job_id=job_id)
    if payload is None or payload.kind != "drilldown":
        raise HTTPException(status_code=404, detail=f"drilldown job no encontrado: {job_id}")
    return DrilldownJobResponse(**payload.model_dump())
