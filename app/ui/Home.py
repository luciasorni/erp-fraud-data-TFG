from __future__ import annotations

import streamlit as st

from app.ui.components.header import configure_page, render_divider, render_home_header, render_section_heading
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.formatters import format_datetime, format_scope
from app.ui.utils.session_state import init_session_state


def main() -> None:
    configure_page(page_title="ERP Fraud Analysis Workbench")
    init_session_state()
    render_home_header()

    client = APIClient()
    runs = []
    try:
        runs = client.list_runs()[:2]
    except APIClientError as exc:
        st.warning(f"No se pudo cargar la actividad reciente: {exc}")

    lead, side = st.columns([1.4, 1.0], gap="large")
    with lead:
        render_section_heading(
            title="Empieza por la acción principal",
            subtitle="La aplicación está pensada para un flujo sencillo: registrar dataset, lanzar análisis y revisar resultados con drilldown seguro.",
        )
        cta1, cta2 = st.columns(2)
        with cta1:
            st.page_link("pages/1_Nuevo_analisis.py", label="Nuevo análisis", icon=":material/play_circle:")
        with cta2:
            st.page_link("pages/2_Ejecuciones.py", label="Ir a ejecuciones", icon=":material/history:")
        st.markdown(
            """
            <div class="rf20-mini-note" style="margin-top:0.55rem;">
                Usa <strong>Nuevo análisis</strong> si vas a cargar un ERP o configurar un run nuevo.
                Ve a <strong>Ejecuciones</strong> si quieres revisar resultados ya lanzados.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with side:
        st.markdown(
            """
            <div class="rf20-callout">
                <div class="rf20-section-title">Qué resuelve esta herramienta</div>
                <div class="rf20-section-copy">
                    Orquesta análisis antifraude ERP sobre P2P y O2C, recupera artefactos del grafo en formato legible y
                    permite investigación detallada sin exponer SQL libre.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_divider()
    with st.expander("Ver actividad reciente", expanded=False):
        render_section_heading(
            title="Últimos análisis",
            subtitle="Solo se muestran uno o dos runs recientes para no convertir la entrada en un dashboard.",
        )
        if runs:
            for run in runs:
                st.markdown(
                    f"""
                    <div class="rf20-list">
                        <div class="rf20-list-item">
                            <div class="rf20-list-title">{run.get("run_id")}</div>
                            <div class="rf20-list-subtitle">{run.get("dataset_id") or "-"} · {format_scope(run.get("scope"))} · {format_datetime(run.get("created_at_utc"))}</div>
                            <div class="rf20-meta-line">Estado: <span class="rf20-meta-inline">{run.get("status") or "-"}</span></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("Todavía no hay actividad reciente disponible.")
        st.page_link("pages/2_Ejecuciones.py", label="Ver historial completo", icon=":material/open_in_new:")


if __name__ == "__main__":
    main()
