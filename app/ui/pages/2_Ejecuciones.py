from __future__ import annotations

from datetime import date
import time

import streamlit as st

from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
from app.ui.components.run_metrics import render_run_metrics
from app.ui.components.run_table import render_run_table
from app.ui.components.status_badge import render_status_badge
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.formatters import format_bool, format_datetime, format_scope
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


def _render_featured_run(run: dict) -> None:
    lead, side = st.columns([4.2, 1.0], gap="large")
    with lead:
        st.markdown(
            f"""
            <div class="rf20-callout">
                <div class="rf20-eyebrow">Última ejecución</div>
                <div class="rf20-title" style="font-size:1.3rem; margin-bottom:0.15rem;">{run.get("run_id")}</div>
                <div class="rf20-subtitle">{run.get("dataset_id") or "-"} · {format_scope(run.get("scope"))} · {format_datetime(run.get("created_at_utc"))}</div>
                <div class="rf20-summary-strip">
                    <div class="rf20-summary-item"><div class="rf20-summary-label">KB rebuild</div><div class="rf20-summary-value">{format_bool(run.get("kb_index_enabled"))}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Graph status</div><div class="rf20-summary-value">{run.get("graph_status") or "-"}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">KB index</div><div class="rf20-summary-value">{run.get("kb_index_status") or "-"}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Última act.</div><div class="rf20-summary-value">{format_datetime(run.get("updated_at_utc"))}</div></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with side:
        render_status_badge(run.get("status"))


def main() -> None:
    configure_page(page_title="Ejecuciones")
    init_session_state()
    render_page_header(
        title="Ejecuciones",
        subtitle="Revisa la ejecución más reciente y navega después por el historial completo de análisis.",
    )

    client = APIClient()
    runs = []
    try:
        runs = client.list_runs()
    except APIClientError as exc:
        st.error(f"No se pudieron cargar las ejecuciones: {exc}")

    render_section_heading(
        title="Visión rápida",
        subtitle="Empieza por la ejecución más reciente. El historial completo queda más abajo para no saturar la entrada.",
    )
    render_run_metrics(build_execution_metrics(runs))

    if runs:
        _render_featured_run(runs[0])
        if str(runs[0].get("status", "")).upper() in {"RUNNING", "SUBMITTED"}:
            st.info("Hay una ejecución en curso. El historial se refresca automáticamente cada 10 segundos para mostrar actividad.")
        if st.button("Abrir esta ejecución", type="primary"):
            remember_run_selection(run_id=runs[0]["run_id"])
            st.switch_page("pages/3_Resultados.py")
    else:
        st.info("Todavía no hay ejecuciones registradas.")

    render_divider()
    render_section_heading(
        title="Historial",
        subtitle="Filtra por dataset, scope, estado o fecha si necesitas localizar una ejecución concreta.",
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

    def _open_run(run_id: str) -> None:
        remember_run_selection(run_id=run_id)
        st.switch_page("pages/3_Resultados.py")

    render_run_table(filtered_runs, on_open=_open_run)

    if any(str(item.get("status", "")).upper() in {"RUNNING", "SUBMITTED"} for item in runs):
        time.sleep(10)
        st.rerun()


if __name__ == "__main__":
    main()
