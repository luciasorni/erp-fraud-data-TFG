from __future__ import annotations

import streamlit as st

from app.ui.components.drilldown_table import render_drilldown_table
from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_detail import render_finding_detail
from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
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
        subtitle="Analiza el caso de forma guiada: resumen, explicación, evidencia, recomendaciones y drilldown.",
    )

    run_id = st.session_state.selected_run_id
    finding = st.session_state.selected_finding
    graph = st.session_state.selected_graph_payload
    if not run_id:
        st.info("Selecciona antes un run desde Resultados o Ejecuciones.")
        return
    if not graph:
        st.info("No hay contexto de resultados cargado para este hallazgo.")
        return

    render_finding_detail(finding)

    explanation = explanation_for_test(graph.get("explanations", []), finding.get("test_id") if finding else None)
    recommendations = recommendations_for_finding(graph.get("second_level_analysis", []))

    render_section_heading(
        title="Qué se ha detectado",
        subtitle="Lectura narrativa del hallazgo para entender por qué el caso merece revisión.",
    )
    render_explanations_panel([explanation] if explanation else [])

    render_divider()
    render_section_heading(
        title="Evidencia principal",
        subtitle="Claves de negocio mínimas conservadas para profundizar en el caso sin romper las guardas de seguridad.",
    )
    if finding and finding.get("sample_keys"):
        st.table([{"campo": key, "valor": value} for key, value in finding["sample_keys"].items()])
    else:
        st.info("No hay claves de evidencia disponibles para este hallazgo.")

    render_divider()
    render_section_heading(
        title="Recomendaciones",
        subtitle="Orientación para investigación, contraste y siguiente paso operativo.",
    )
    render_recommendations_panel(recommendations)

    render_divider()
    render_section_heading(
        title="Drilldown",
        subtitle="Ejecuta recuperación de evidencia detallada a partir de las claves del hallazgo.",
    )
    if not finding or not finding.get("sample_keys"):
        st.info("Este hallazgo no dispone de claves mínimas para ejecutar drilldown.")
        return

    client = APIClient()
    controls = st.columns([1.2, 1.0, 1.0, 1.2])
    action = controls[0].selectbox("Acción", ALLOWED_DRILLDOWN_ACTIONS)
    limit_rows = controls[1].slider("Límite", min_value=10, max_value=200, value=50, step=10)
    order_direction = controls[2].selectbox("Orden", ["ASC", "DESC"])
    if controls[3].button("Ejecutar drilldown", type="primary", use_container_width=True):
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
