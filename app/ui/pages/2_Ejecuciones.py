from __future__ import annotations

from datetime import date

import streamlit as st

from app.ui.components.header import configure_page, render_page_header
from app.ui.components.run_metrics import render_run_metrics
from app.ui.components.run_table import render_run_table
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.mappers import build_execution_metrics
from app.ui.utils.session_state import init_session_state, remember_run_selection


def _matches_filters(run: dict, filters: dict) -> bool:
    if filters["dataset"] != "Todos" and run.get("dataset_id") != filters["dataset"]:
        return False
    if filters["scope"] != "Todos" and run.get("scope") != filters["scope"]:
        return False
    if filters["status"] != "Todos" and run.get("status") != filters["status"]:
        return False
    if filters["date_from"]:
        created_at = str(run.get("created_at_utc") or "")
        if not created_at.startswith(filters["date_from"].isoformat()):
            return False
    return True


def main() -> None:
    configure_page(page_title="Ejecuciones")
    init_session_state()
    render_page_header(
        title="Ejecuciones",
        subtitle="Consulta el estado y el historial de análisis realizados.",
    )

    client = APIClient()
    runs = []
    try:
        runs = client.list_runs()
    except APIClientError as exc:
        st.error(f"No se pudieron cargar las ejecuciones: {exc}")

    render_run_metrics(build_execution_metrics(runs))

    st.markdown(
        """
        <div class="rf20-section soft">
            <div class="rf20-section-title">Filtros</div>
            <div class="rf20-section-copy">Acota el historial por dataset, scope, estado o fecha para localizar runs concretos.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    datasets = ["Todos"] + sorted({item.get("dataset_id") for item in runs if item.get("dataset_id")})
    scopes = ["Todos"] + sorted({item.get("scope") for item in runs if item.get("scope")})
    statuses = ["Todos"] + sorted({item.get("status") for item in runs if item.get("status")})
    col1, col2, col3, col4 = st.columns(4)
    filters = st.session_state.runs_filters
    filters["dataset"] = col1.selectbox("Dataset", datasets, index=datasets.index(filters["dataset"]) if filters["dataset"] in datasets else 0)
    filters["scope"] = col2.selectbox("Scope", scopes, index=scopes.index(filters["scope"]) if filters["scope"] in scopes else 0)
    filters["status"] = col3.selectbox("Estado", statuses, index=statuses.index(filters["status"]) if filters["status"] in statuses else 0)
    filters["date_from"] = col4.date_input("Desde", value=filters["date_from"] or None, format="DD/MM/YYYY")
    if filters["date_from"] == date.min:
        filters["date_from"] = None

    filtered_runs = [item for item in runs if _matches_filters(item, filters)]

    st.markdown(
        """
        <div class="rf20-section">
            <div class="rf20-section-title">Historial de ejecuciones</div>
            <div class="rf20-section-copy">Cada run muestra su contexto operativo y un acceso directo a resultados.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    def _open_run(run_id: str) -> None:
        remember_run_selection(run_id=run_id)
        st.switch_page("pages/3_Resultados.py")

    render_run_table(filtered_runs, on_open=_open_run)


if __name__ == "__main__":
    main()
