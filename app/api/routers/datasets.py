from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..schemas.datasets import DatasetDetailResponse, DatasetSummaryResponse, DatasetUploadResponse
from ..services.aws_service import load_aws_api_settings
from ..services.datasets_service import get_dataset, list_datasets, upload_dataset


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


@router.get("/datasets", response_model=list[DatasetSummaryResponse])
def get_datasets() -> list[DatasetSummaryResponse]:
    return list_datasets(settings=load_aws_api_settings())


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset_detail(dataset_id: str) -> DatasetDetailResponse:
    payload = get_dataset(dataset_id=dataset_id, settings=load_aws_api_settings())
    if payload is None:
        raise HTTPException(status_code=404, detail=f"dataset_id no encontrado: {dataset_id}")
    return payload

