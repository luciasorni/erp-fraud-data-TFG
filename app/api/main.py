from __future__ import annotations

from fastapi import FastAPI

from src.erp_fraud.config import env as _erp_env  # noqa: F401

from .routers.datasets import router as datasets_router
from .routers.drilldown import router as drilldown_router
from .routers.health import router as health_router
from .routers.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ERP Fraud Application API",
        version="1.0.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
    )
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(datasets_router, prefix="/api/v1", tags=["datasets"])
    app.include_router(runs_router, prefix="/api/v1", tags=["runs"])
    app.include_router(drilldown_router, prefix="/api/v1", tags=["drilldown"])
    return app


app = create_app()
