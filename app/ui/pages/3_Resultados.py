from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_list import render_findings_list
from app.ui.components.header import configure_page, render_page_header
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
            <div class="rf20-panel soft">
                <div class="rf20-heading">{item.get('title') or item.get('id') or 'Hypothesis'}</div>
                <div class="rf20-subline">{item.get("subtitle") or ""}</div>
                <div class="rf20-body">{item.get("summary") or "Sin resumen."}</div>
                <div class="rf20-inline-note">Tests candidatos: {", ".join(attrs.get("candidate_test_ids", [])) or "-"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_selected_tests(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay tests seleccionados.")
        return
    for item in items:
        attrs = item.get("attributes") or {}
        st.markdown(
            f"""
            <div class="rf20-panel">
                <div class="rf20-row">
                    <div>
                        <div class="rf20-heading">{item.get("id") or "-"}</div>
                        <div class="rf20-subline">{item.get("subtitle") or "-"}</div>
                    </div>
                    <div class="rf20-inline-note">Origen: {item.get("status") or "-"}</div>
                </div>
                <div class="rf20-body">{item.get("summary") or "Sin motivo de selección detallado."}</div>
                <div class="rf20-meta-grid">
                    <div class="rf20-meta-item">
                        <div class="rf20-meta-label">Test asociado</div>
                        <div class="rf20-meta-value">{item.get("id") or "-"}</div>
                    </div>
                    <div class="rf20-meta-item">
                        <div class="rf20-meta-label">Fraud type</div>
                        <div class="rf20-meta-value">{item.get("subtitle") or "-"}</div>
                    </div>
                    <div class="rf20-meta-item">
                        <div class="rf20-meta-label">Score</div>
                        <div class="rf20-meta-value">{attrs.get("score", "-")}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
        subtitle="Consulta hypotheses, tests seleccionados, hallazgos, explicaciones y recomendaciones del run.",
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

    detail = None
    graph = None
    report = None
    try:
        detail = client.get_run(selected_run_id)
        graph = client.get_run_graph(selected_run_id)
        report = client.get_run_report(selected_run_id)
        remember_run_selection(run_id=selected_run_id, run_detail=detail)
        st.session_state.selected_graph_payload = graph
    except APIClientError as exc:
        st.error(f"No se pudieron cargar los resultados del run: {exc}")
        return

    st.markdown(
        f"""
        <div class="rf20-section">
            <div class="rf20-row">
                <div>
                    <div class="rf20-kicker">Run seleccionado</div>
                    <div class="rf20-title" style="font-size:1.35rem; margin-bottom:0.15rem;">{detail.get('run_id')}</div>
                    <div class="rf20-subline">{detail.get("dataset_id") or "-"} · {format_scope(detail.get("scope"))} · {format_datetime(detail.get("created_at_utc"))}</div>
                </div>
                <div class="rf20-inline-note">KB rebuild: <strong>{format_bool(detail.get('kb_index_enabled'))}</strong></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_status_badge(detail.get("status"))

    scores = graph.get("scores", [])
    score_value = "-"
    if scores:
        maybe = extract_score_value(scores[0])
        if maybe is not None:
            score_value = f"{maybe:.2f}"
    render_result_kpis(build_run_kpis(graph), score_value=score_value)

    st.markdown(
        """
        <div class="rf20-section soft">
            <div class="rf20-section-title">Resultados del análisis</div>
            <div class="rf20-section-copy">Explora hipótesis, tests seleccionados, hallazgos, scoring, explicación narrativa y recomendaciones en capas separadas.</div>
        </div>
        """,
        unsafe_allow_html=True,
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

    with st.expander("Detalle técnico del run"):
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
