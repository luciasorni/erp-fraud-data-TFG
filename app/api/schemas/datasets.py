from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal

from pydantic import Field

from .common import APIModel


DatasetScope = Literal["p2p", "o2c", "both"]


class DatasetUploadResponse(APIModel):
    dataset_id: str
    file_name: str
    scopes: List[Literal["p2p", "o2c"]]
    validation_status: str
    files_detected: List[str]
    expected_files: List[str]
    dataset_hash: str
    uploaded_at_utc: datetime
    s3_keys: Dict[str, str]
    size_bytes: int = Field(ge=0)


class DatasetSummaryResponse(APIModel):
    dataset_id: str
    file_name: str
    scopes: List[Literal["p2p", "o2c"]]
    validation_status: str
    dataset_hash: str
    uploaded_at_utc: datetime


class DatasetDetailResponse(APIModel):
    dataset_id: str
    file_name: str
    scopes: List[Literal["p2p", "o2c"]]
    validation_status: str
    dataset_hash: str
    uploaded_at_utc: datetime
    files_detected: List[str]
    expected_files: List[str]
    s3_keys: Dict[str, str]
    metadata_key: str
    size_bytes: int = Field(ge=0)
