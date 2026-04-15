from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..schemas.datasets import DatasetDetailResponse, DatasetSummaryResponse, DatasetUploadJobResponse, DatasetUploadResponse
from ..services.aws_service import load_aws_api_settings
from ..services.datasets_service import get_dataset, list_datasets, upload_dataset, upload_dataset_from_bytes
from ..services.operations_service import create_job, get_job, run_job_in_thread, update_job


router = APIRouter()


@router.post("/datasets/upload", response_model=DatasetUploadResponse)
def post_dataset_upload(
    file: UploadFile = File(...),
    scope: str = Form(...),
) -> DatasetUploadResponse:
    try:
        return upload_dataset(file=file, scope=scope, settings=load_aws_api_settings())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/datasets/upload-jobs", response_model=DatasetUploadJobResponse, status_code=202)
def post_dataset_upload_job(
    file: UploadFile = File(...),
    scope: str = Form(...),
) -> DatasetUploadJobResponse:
    settings = load_aws_api_settings()
    file_name = str(file.filename or "").strip() or "erp_fraud_data.zip"
    body = file.file.read()
    job = create_job(kind="dataset_upload", stage="received", message="Solicitud de upload recibida.")

    def _status_callback(*, stage: str, message: str, progress: int) -> None:
        update_job(job_id=job.job_id, status="RUNNING", stage=stage, message=message, progress=progress)

    def _target() -> dict:
        payload = upload_dataset_from_bytes(
            file_name=file_name,
            body=body,
            scope=scope,
            settings=settings,
            status_callback=_status_callback,
        )
        return payload.model_dump(mode="json")

    run_job_in_thread(job_id=job.job_id, target=_target)
    return DatasetUploadJobResponse(**job.model_dump())


@router.get("/datasets/upload-jobs/{job_id}", response_model=DatasetUploadJobResponse)
def get_dataset_upload_job(job_id: str) -> DatasetUploadJobResponse:
    payload = get_job(job_id=job_id)
    if payload is None or payload.kind != "dataset_upload":
        raise HTTPException(status_code=404, detail=f"dataset upload job no encontrado: {job_id}")
    return DatasetUploadJobResponse(**payload.model_dump())


@router.get("/datasets", response_model=list[DatasetSummaryResponse])
def get_datasets() -> list[DatasetSummaryResponse]:
    return list_datasets(settings=load_aws_api_settings())


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset_detail(dataset_id: str) -> DatasetDetailResponse:
    payload = get_dataset(dataset_id=dataset_id, settings=load_aws_api_settings())
    if payload is None:
        raise HTTPException(status_code=404, detail=f"dataset_id no encontrado: {dataset_id}")
    return payload
