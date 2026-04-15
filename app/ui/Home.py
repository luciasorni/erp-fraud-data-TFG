from __future__ import annotations

import streamlit as st

from app.ui.components.header import configure_page, render_home_header
from app.ui.components.run_metrics import render_run_metrics
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.mappers import build_execution_metrics
from app.ui.utils.session_state import init_session_state


def main() -> None:
    configure_page(page_title="ERP Fraud Analysis Workbench")
    init_session_state()
    render_home_header()

    client = APIClient()
    runs = []
    health = None
    try:
        health = client.get_health()
        runs = client.list_runs()[:6]
    except APIClientError as exc:
        st.warning(f"No se pudo conectar con la API: {exc}")

    left, right = st.columns([1.4, 1.0])
    with left:
        st.markdown(
            """
            <div class="rf20-section">
                <div class="rf20-section-title">Qué puedes hacer desde aquí</div>
                <div class="rf20-section-copy">
                    Registrar datasets ERP controlados, lanzar análisis cloud en <code>graph</code>, seguir el estado de cada run
                    y revisar hallazgos, explicaciones y recomendaciones de investigación con drilldown seguro.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cta1, cta2 = st.columns(2)
        with cta1:
            st.page_link("pages/1_Nuevo_analisis.py", label="Nuevo análisis", icon=":material/add_circle:")
        with cta2:
            st.page_link("pages/2_Ejecuciones.py", label="Ver ejecuciones", icon=":material/monitoring:")
    with right:
        st.markdown(
            """
            <div class="rf20-section soft">
                <div class="rf20-section-title">Estado del sistema</div>
                <div class="rf20-section-copy">Arquitectura backend cloud validada sobre AWS y consumida vía <code>/api/v1</code>.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric("API", "Operativa" if health and health.get("status") == "ok" else "Sin conexión")

    st.markdown("### Actividad reciente")
    render_run_metrics(build_execution_metrics(runs))
    if runs:
        for run in runs[:4]:
            st.markdown(
                f"""
                <div class="rf20-panel soft">
                    <div class="rf20-heading">{run.get('run_id')}</div>
                    <div class="rf20-subline">{run.get('dataset_id') or '-'} · {run.get('scope') or '-'} · {run.get('status') or '-'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("Todavía no hay ejecuciones recientes disponibles.")


if __name__ == "__main__":
    main()
