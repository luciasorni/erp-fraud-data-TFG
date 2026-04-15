from __future__ import annotations

import streamlit as st

from app.ui.components.drilldown_table import render_drilldown_table
from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_detail import render_finding_detail
from app.ui.components.header import configure_page, render_page_header
from app.ui.components.recommendations_panel import render_recommendations_panel
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.constants import ALLOWED_DRILLDOWN_ACTIONS
from app.ui.utils.mappers import explanation_for_test, recommendations_for_finding
from app.ui.utils.session_state import init_session_state


def main() -> None:
    configure_page(page_title="Detalle del hallazgo")
    init_session_state()
    render_page_header(
        title="Detalle del hallazgo",
        subtitle="Investiga qué se detectó, cuál es la evidencia asociada y qué siguiente paso se recomienda.",
    )

    run_id = st.session_state.selected_run_id
    finding = st.session_state.selected_finding
    graph = st.session_state.selected_graph_payload
    if not run_id:
        st.info("Selecciona antes un run desde la página de Resultados o Ejecuciones.")
        return
    if not graph:
        st.info("No hay contexto de resultados cargado para este hallazgo.")
        return

    render_finding_detail(finding)

    explanation = explanation_for_test(graph.get("explanations", []), finding.get("test_id") if finding else None)
    recommendations = recommendations_for_finding(graph.get("second_level_analysis", []))

    st.markdown(
        """
        <div class="rf20-section soft">
            <div class="rf20-section-title">Qué se ha detectado</div>
            <div class="rf20-section-copy">Interpretación narrativa del hallazgo a partir de la explicación del run.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_explanations_panel([explanation] if explanation else [])

    st.markdown(
        """
        <div class="rf20-section">
            <div class="rf20-section-title">Evidencia principal</div>
            <div class="rf20-section-copy">Claves mínimas conservadas para investigación y drilldown seguro.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if finding and finding.get("sample_keys"):
        st.table([{"campo": key, "valor": value} for key, value in finding["sample_keys"].items()])
    else:
        st.info("No hay claves de evidencia disponibles para este hallazgo.")

    st.markdown(
        """
        <div class="rf20-section toned">
            <div class="rf20-section-title">Recomendaciones</div>
            <div class="rf20-section-copy">Siguientes pasos sugeridos para investigación y contraste.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_recommendations_panel(recommendations)

    st.markdown(
        """
        <div class="rf20-section soft">
            <div class="rf20-section-title">Drilldown</div>
            <div class="rf20-section-copy">Recupera evidencia detallada del dataset sin exponer SQL libre.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not finding or not finding.get("sample_keys"):
        st.info("Este hallazgo no dispone de claves mínimas para ejecutar drilldown.")
        return

    client = APIClient()
    col1, col2, col3 = st.columns([1.2, 1.0, 1.0])
    action = col1.selectbox("Acción", ALLOWED_DRILLDOWN_ACTIONS)
    limit_rows = col2.slider("Límite de filas", min_value=10, max_value=200, value=50, step=10)
    order_direction = col3.selectbox("Orden", ["ASC", "DESC"])

    if st.button("Ejecutar drilldown", type="primary"):
        try:
            payload = client.post_drilldown(
                run_id=run_id,
                action=action,
                test_id=finding.get("test_id") or "",
                keys=finding.get("sample_keys") or {},
                limit_rows=limit_rows,
                order_direction=order_direction,
            )
            st.session_state.drilldown_result = payload
            st.success("Drilldown ejecutado correctamente.")
        except APIClientError as exc:
            st.error(f"No se pudo ejecutar el drilldown: {exc}")

    render_drilldown_table(st.session_state.drilldown_result)


if __name__ == "__main__":
    main()
