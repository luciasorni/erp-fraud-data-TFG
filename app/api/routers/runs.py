from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..schemas.results import GraphResultsResponse, ReportResponse
from ..schemas.runs import RunCreateRequest, RunCreateResponse, RunDetailResponse, RunSummaryResponse
from ..services.aws_service import load_aws_api_settings
from ..services.results_service import load_graph_results, load_report
from ..services.runs_service import create_run, get_run, list_runs


router = APIRouter()


@router.post("/runs", response_model=RunCreateResponse)
def post_runs(payload: RunCreateRequest) -> RunCreateResponse:
    try:
        return create_run(payload=payload, settings=load_aws_api_settings())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs", response_model=list[RunSummaryResponse])
def get_runs(limit: int = Query(default=20, ge=1, le=200)) -> list[RunSummaryResponse]:
    return list_runs(settings=load_aws_api_settings(), limit=limit)


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run_detail(run_id: str) -> RunDetailResponse:
    payload = get_run(run_id=run_id, settings=load_aws_api_settings())
    if payload is None:
        raise HTTPException(status_code=404, detail=f"run_id no encontrado: {run_id}")
    return payload


@router.get("/runs/{run_id}/graph", response_model=GraphResultsResponse)
def get_run_graph(run_id: str) -> GraphResultsResponse:
    detail = get_run(run_id=run_id, settings=load_aws_api_settings())
    if detail is None:
        raise HTTPException(status_code=404, detail=f"run_id no encontrado: {run_id}")
    return load_graph_results(
        run_id=run_id,
        status=detail.status,
        scope=detail.scope,
        settings=load_aws_api_settings(),
    )


@router.get("/runs/{run_id}/report", response_model=ReportResponse)
def get_run_report(run_id: str) -> ReportResponse:
    detail = get_run(run_id=run_id, settings=load_aws_api_settings())
    if detail is None:
        raise HTTPException(status_code=404, detail=f"run_id no encontrado: {run_id}")
    return load_report(
        run_id=run_id,
        status=detail.status,
        scope=detail.scope,
        settings=load_aws_api_settings(),
    )
