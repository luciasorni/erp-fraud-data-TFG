from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_list import render_findings_list
from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
from app.ui.components.recommendations_panel import render_recommendations_panel
from app.ui.components.run_metrics import render_result_kpis
from app.ui.components.status_badge import render_status_badge
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.formatters import format_bool, format_datetime, format_scope
from app.ui.utils.mappers import build_run_kpis, extract_score_value, findings_table_rows
from app.ui.utils.session_state import init_session_state, remember_finding_selection, remember_run_selection


def _render_hypotheses(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay hipótesis generadas para este run.")
        return
    for item in items:
        attrs = item.get("attributes", {}) or {}
        st.markdown(
            f"""
            <div class="rf20-narrative">
                <div class="rf20-list-title">{item.get('title') or item.get('id') or 'Hypothesis'}</div>
                <div class="rf20-list-subtitle">{item.get("subtitle") or ""}</div>
                <div class="rf20-meta-line">{item.get("summary") or "Sin resumen."}</div>
                <div class="rf20-mini-note">Tests candidatos: {", ".join(attrs.get("candidate_test_ids", [])) or "-"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_selected_tests(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay tests seleccionados.")
        return
    st.markdown('<div class="rf20-list">', unsafe_allow_html=True)
    for item in items:
        attrs = item.get("attributes") or {}
        st.markdown(
            f"""
            <div class="rf20-list-item">
                <div class="rf20-list-title">{item.get("id") or "-"}</div>
                <div class="rf20-list-subtitle">{item.get("subtitle") or "-"}</div>
                <div class="rf20-meta-line">{item.get("summary") or "Sin motivo de selección detallado."}</div>
                <div class="rf20-meta-line">
                    Origen: <span class="rf20-meta-inline">{item.get("status") or "-"}</span>
                    &nbsp;&nbsp;·&nbsp;&nbsp;
                    Score: <span class="rf20-meta-inline">{attrs.get("score", "-")}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_scores(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay scoring agregado disponible.")
        return
    rows = []
    for item in items:
        rows.append(
            {
                "label": item.get("id"),
                "confidence": extract_score_value(item),
                "source": item.get("status"),
                "summary": item.get("summary"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def main() -> None:
    configure_page(page_title="Resultados")
    init_session_state()
    render_page_header(
        title="Resultados del análisis",
        subtitle="Lee el run actual como una investigación guiada: contexto, volumen, hallazgos, explicación y recomendaciones.",
    )

    client = APIClient()
    runs = []
    try:
        runs = client.list_runs()
    except APIClientError as exc:
        st.error(f"No se pudo cargar el historial de runs: {exc}")

    run_ids = [item["run_id"] for item in runs]
    selected_run_id = st.session_state.selected_run_id if st.session_state.selected_run_id in run_ids else (run_ids[0] if run_ids else None)
    selected_run_id = st.selectbox("Run", run_ids, index=run_ids.index(selected_run_id) if selected_run_id in run_ids else 0) if run_ids else None
    if not selected_run_id:
        st.info("Todavía no hay runs disponibles.")
        return

    try:
        detail = client.get_run(selected_run_id)
        graph = client.get_run_graph(selected_run_id)
        report = client.get_run_report(selected_run_id)
        remember_run_selection(run_id=selected_run_id, run_detail=detail)
        st.session_state.selected_graph_payload = graph
    except APIClientError as exc:
        st.error(f"No se pudieron cargar los resultados del run: {exc}")
        return

    top_left, top_right = st.columns([5.0, 1.0], gap="large")
    with top_left:
        st.markdown(
            f"""
            <div class="rf20-pagehead" style="padding-bottom:0.8rem; margin-bottom:0.9rem;">
                <div class="rf20-eyebrow">Run actual</div>
                <div class="rf20-title" style="font-size:1.35rem; margin-bottom:0.15rem;">{detail.get("run_id")}</div>
                <div class="rf20-subtitle">{detail.get("dataset_id") or "-"} · {format_scope(detail.get("scope"))} · {format_datetime(detail.get("created_at_utc"))}</div>
                <div class="rf20-meta-line" style="margin-top:0.55rem;">
                    KB rebuild: <span class="rf20-meta-inline">{format_bool(detail.get("kb_index_enabled"))}</span>
                    &nbsp;&nbsp;·&nbsp;&nbsp;
                    Graph status: <span class="rf20-meta-inline">{graph.get("graph_status") or "-"}</span>
                    &nbsp;&nbsp;·&nbsp;&nbsp;
                    KB index: <span class="rf20-meta-inline">{graph.get("kb_index_status") or "-"}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with top_right:
        render_status_badge(detail.get("status"))

    scores = graph.get("scores", [])
    score_value = "-"
    if scores:
        maybe = extract_score_value(scores[0])
        if maybe is not None:
            score_value = f"{maybe:.2f}"
    render_result_kpis(build_run_kpis(graph), score_value=score_value)

    render_divider()
    render_section_heading(
        title="Lectura del resultado",
        subtitle="Usa las pestañas para moverte entre hipótesis, tests, hallazgos, scoring, explicación y siguientes pasos.",
    )
    tab_hyp, tab_tests, tab_findings, tab_scores, tab_expl, tab_rec = st.tabs(
        ["Hypotheses", "Selected tests", "Findings", "Scores", "Explicación", "Recomendaciones"]
    )

    with tab_hyp:
        _render_hypotheses(graph.get("hypotheses", []))
    with tab_tests:
        _render_selected_tests(graph.get("selected_tests", []))
    with tab_findings:
        finding_rows = findings_table_rows(graph.get("findings", []))

        def _open_detail(row: dict) -> None:
            remember_finding_selection(finding_id=row.get("finding_id") or "", finding=row)
            st.switch_page("pages/4_Detalle_hallazgo.py")

        render_findings_list(finding_rows, on_select=_open_detail)
    with tab_scores:
        _render_scores(scores)
    with tab_expl:
        render_explanations_panel(graph.get("explanations", []))
    with tab_rec:
        render_recommendations_panel(graph.get("second_level_analysis", []))

    with st.expander("Detalle técnico del run", expanded=False):
        st.write(
            {
                "graph_status": graph.get("graph_status"),
                "kb_index_status": graph.get("kb_index_status"),
                "report_overall_status": report.get("overall_status"),
                "artifact_keys": detail.get("artifact_keys", {}),
            }
        )


if __name__ == "__main__":
    main()
