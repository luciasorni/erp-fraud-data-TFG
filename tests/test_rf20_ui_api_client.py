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
