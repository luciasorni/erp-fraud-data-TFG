from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from app.ui.utils.constants import API_BASE_URL


class APIClientError(RuntimeError):
    pass


class APIClient:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout_seconds: int = 30,
    ) -> None:
        env_url = str(os.getenv("ERP_FRAUD_API_BASE_URL", "")).strip()
        self.base_url = (base_url or env_url or API_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _handle_response(self, response: requests.Response) -> Any:
        if response.ok:
            if not response.content:
                return None
            return response.json()
        try:
            payload = response.json()
            detail = payload.get("detail") or payload
        except Exception:
            detail = response.text
        raise APIClientError(f"API {response.status_code}: {detail}")

    def _get(self, path: str, *, timeout: Optional[int] = None) -> Any:
        try:
            response = self.session.get(self._url(path), timeout=timeout or self.timeout_seconds)
        except requests.exceptions.Timeout as exc:
            raise APIClientError("La operación tardó demasiado en responder.") from exc
        except requests.RequestException as exc:
            raise APIClientError(f"No se pudo conectar con la API: {exc}") from exc
        return self._handle_response(response)

    def _post(self, path: str, *, timeout: Optional[int] = None, **kwargs: Any) -> Any:
        try:
            response = self.session.post(self._url(path), timeout=timeout or self.timeout_seconds, **kwargs)
        except requests.exceptions.Timeout as exc:
            raise APIClientError("La operación tardó demasiado en responder.") from exc
        except requests.RequestException as exc:
            raise APIClientError(f"No se pudo conectar con la API: {exc}") from exc
        return self._handle_response(response)

    def get_health(self) -> Dict[str, Any]:
        return self._get("health")

    def list_datasets(self) -> list[dict[str, Any]]:
        return self._get("datasets")

    def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        return self._get(f"datasets/{dataset_id}")

    def upload_dataset(self, *, file_name: str, file_bytes: bytes, scope: str) -> Dict[str, Any]:
        return self._post(
            "datasets/upload",
            data={"scope": scope},
            files={"file": (file_name, file_bytes, "application/zip")},
        )

    def start_upload_dataset_job(self, *, file_name: str, file_bytes: bytes, scope: str) -> Dict[str, Any]:
        return self._post(
            "datasets/upload-jobs",
            data={"scope": scope},
            files={"file": (file_name, file_bytes, "application/zip")},
            timeout=15,
        )

    def get_upload_dataset_job(self, job_id: str) -> Dict[str, Any]:
        return self._get(f"datasets/upload-jobs/{job_id}", timeout=10)

    def create_run(
        self,
        *,
        dataset_id: str,
        scope: str,
        pipeline_mode: str,
        llm_mode: str,
        kb_index_enabled: bool,
    ) -> Dict[str, Any]:
        return self._post(
            "runs",
            json={
                "dataset_id": dataset_id,
                "scope": scope,
                "pipeline_mode": pipeline_mode,
                "llm_mode": llm_mode,
                "kb_index_enabled": kb_index_enabled,
            },
        )

    def list_runs(self) -> list[dict[str, Any]]:
        return self._get("runs")

    def get_run(self, run_id: str) -> Dict[str, Any]:
        return self._get(f"runs/{run_id}")

    def get_run_graph(self, run_id: str) -> Dict[str, Any]:
        return self._get(f"runs/{run_id}/graph")

    def get_run_report(self, run_id: str) -> Dict[str, Any]:
        return self._get(f"runs/{run_id}/report")

    def post_drilldown(
        self,
        *,
        run_id: str,
        action: str,
        test_id: str,
        keys: Dict[str, str],
        limit_rows: int = 50,
        order_direction: str = "ASC",
        extra_filters: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return self._post(
            f"runs/{run_id}/drilldown",
            json={
                "action": action,
                "test_id": test_id,
                "keys": keys,
                "limit_rows": limit_rows,
                "order_direction": order_direction,
                "extra_filters": extra_filters or {},
            },
        )

    def start_drilldown_job(
        self,
        *,
        run_id: str,
        action: str,
        test_id: str,
        keys: Dict[str, str],
        limit_rows: int = 50,
        order_direction: str = "ASC",
        extra_filters: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return self._post(
            f"runs/{run_id}/drilldown-jobs",
            json={
                "action": action,
                "test_id": test_id,
                "keys": keys,
                "limit_rows": limit_rows,
                "order_direction": order_direction,
                "extra_filters": extra_filters or {},
            },
            timeout=15,
        )

    def get_drilldown_job(self, *, run_id: str, job_id: str) -> Dict[str, Any]:
        return self._get(f"runs/{run_id}/drilldown-jobs/{job_id}", timeout=10)
