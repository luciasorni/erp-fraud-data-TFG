from __future__ import annotations

from typing import Any
from pathlib import Path

from app.ui.services.api_client import APIClient, APIClientError


class _FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code < 400
        self.content = b"{}"
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


class _FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def get(self, url: str, timeout: int) -> _FakeResponse:
        self.calls.append(("GET", url, timeout))
        return _FakeResponse({"status": "ok"})

    def post(self, url: str, timeout: int, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("POST", url, timeout, kwargs))
        return _FakeResponse({"run_id": "run-001", "composite_run": False})


def test_rf20_ui_api_client_builds_expected_paths() -> None:
    session = _FakeSession()
    client = APIClient(base_url="http://localhost:8000/api/v1", session=session)
    health = client.get_health()
    run = client.create_run(
        dataset_id="ds-001",
        scope="p2p",
        pipeline_mode="graph",
        llm_mode="real",
        kb_index_enabled=False,
    )
    assert health["status"] == "ok"
    assert run["run_id"] == "run-001"
    assert session.calls[0][1] == "http://localhost:8000/api/v1/health"
    assert session.calls[1][1] == "http://localhost:8000/api/v1/runs"


def test_rf20_ui_api_client_raises_on_error() -> None:
    class _ErrorSession(_FakeSession):
        def get(self, url: str, timeout: int) -> _FakeResponse:
            return _FakeResponse({"detail": "boom"}, status_code=500)

    client = APIClient(base_url="http://localhost:8000/api/v1", session=_ErrorSession())
    try:
        client.get_health()
    except APIClientError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("Expected APIClientError")


def test_rf20_ui_pages_use_relative_streamlit_paths() -> None:
    root = Path("app/ui")
    checked = [
        root / "Home.py",
        root / "pages/1_Nuevo_analisis.py",
        root / "pages/2_Ejecuciones.py",
        root / "pages/3_Resultados.py",
    ]
    for path in checked:
        content = path.read_text(encoding="utf-8")
        assert "app/ui/pages/" not in content


def test_rf20_ui_api_client_supports_job_endpoints() -> None:
    session = _FakeSession()
    client = APIClient(base_url="http://localhost:8000/api/v1", session=session)
    upload = client.get_upload_dataset_job("job-001")
    drilldown = client.get_drilldown_job(run_id="run-001", job_id="job-002")
    assert upload["status"] == "ok"
    assert drilldown["status"] == "ok"
    assert session.calls[0][1] == "http://localhost:8000/api/v1/datasets/upload-jobs/job-001"
    assert session.calls[1][1] == "http://localhost:8000/api/v1/runs/run-001/drilldown-jobs/job-002"


def test_rf20_ui_api_client_list_runs_supports_limit() -> None:
    session = _FakeSession()
    client = APIClient(base_url="http://localhost:8000/api/v1", session=session)
    client.list_runs(limit=7)
    assert session.calls[0][1] == "http://localhost:8000/api/v1/runs?limit=7"


def test_rf20_ui_api_client_detail_endpoints_build_expected_paths() -> None:
    session = _FakeSession()
    client = APIClient(base_url="http://localhost:8000/api/v1", session=session)
    client.get_run("run-001")
    client.get_run_graph("run-001")
    client.get_run_report("run-001")
    assert session.calls[0][1] == "http://localhost:8000/api/v1/runs/run-001"
    assert session.calls[1][1] == "http://localhost:8000/api/v1/runs/run-001/graph"
    assert session.calls[2][1] == "http://localhost:8000/api/v1/runs/run-001/report"


def test_rf20_ui_api_client_sends_query_id_for_drilldown() -> None:
    session = _FakeSession()
    client = APIClient(base_url="http://localhost:8000/api/v1", session=session)
    client.start_drilldown_job(
        run_id="run-001",
        action="finding_rows",
        test_id="TST-O2C-DELIVERY-QUANTITY-MISMATCH",
        keys={"delivery_id": "D1", "delivery_item_id": "10"},
        query_id="drilldown_o2c_delivery_quantity_mismatch_v1",
    )
    body = session.calls[0][3]["json"]
    assert body["query_id"] == "drilldown_o2c_delivery_quantity_mismatch_v1"
