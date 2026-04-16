from __future__ import annotations

import streamlit as st

from app.ui.components.header import configure_page, render_divider, render_home_header, render_section_heading
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.formatters import format_datetime, format_scope
from app.ui.utils.session_state import init_session_state


def _list_runs_safe(client: APIClient, *, limit: int) -> list[dict]:
    try:
        return client.list_runs(limit=limit)
    except TypeError:
        runs = client.list_runs()
        return runs[:limit]


def inject_home_local_styles() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #FFFFFF !important;
            border: 1px solid #C9D4CF !important;
            border-radius: 18px !important;
            padding: 1.1rem 1.15rem !important;
            box-shadow: 0 10px 24px rgba(18, 48, 43, 0.06) !important;
        }

        [data-testid="stPageLink"] {
            margin-top: 0.15rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def main() -> None:
    configure_page(page_title="ERP Fraud Analysis Workbench")
    init_session_state()
    st.session_state["_active_page"] = "home"
    render_home_header()
    inject_home_local_styles()

    client = APIClient()
    runs = []
    try:
        runs = _list_runs_safe(client, limit=2)
    except APIClientError as exc:
        st.warning(f"No se pudo cargar la actividad reciente: {exc}")

    lead, side = st.columns([1.55, 0.85], gap="large")

    with lead:
        with st.container(border=True):
            st.markdown('<div class="rf20-home-cta-anchor"></div>', unsafe_allow_html=True)

            render_section_heading(
                title="Empieza por la acción principal",
                subtitle="La aplicación está pensada para un flujo sencillo: registrar dataset, lanzar análisis y revisar resultados con drilldown seguro.",
            )

            cta1, cta2, cta3 = st.columns([1.05, 1.0, 1.35], gap="small")

            with cta1:
                st.page_link(
                    "pages/1_Nuevo_analisis.py",
                    label="Nuevo análisis",
                    icon=":material/play_circle:",
                    use_container_width=True,
                )

            with cta2:
                st.page_link(
                    "pages/2_Ejecuciones.py",
                    label="Ejecuciones",
                    icon=":material/history:",
                    use_container_width=True,
                )

            with cta3:
                st.page_link(
                    "pages/5_Como_funciona.py",
                    label="Cómo funciona",
                    icon=":material/info:",
                    use_container_width=True,
                )

            st.markdown(
                """
                <div class="rf20-mini-note" style="margin-top:0.55rem;">
                    Usa <strong>Nuevo análisis</strong> si vas a cargar un ERP o configurar un run nuevo.
                    Ve a <strong>Ejecuciones</strong> si quieres revisar resultados ya lanzados y a <strong>Cómo funciona</strong>
                    si necesitas contexto sobre P2P, O2C, hypotheses, findings y scoring.
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

        st.page_link(
            "pages/2_Ejecuciones.py",
            label="Ver historial completo",
            icon=":material/open_in_new:",
        )


if __name__ == "__main__":
    main()
