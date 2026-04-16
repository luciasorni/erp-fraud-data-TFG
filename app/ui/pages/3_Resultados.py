from __future__ import annotations

import time
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_list import render_findings_list
from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
from app.ui.components.recommendations_panel import render_presentable_content, render_recommendations_panel
from app.ui.components.run_metrics import render_result_kpis
from app.ui.components.status_badge import render_status_badge
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.formatters import format_bool, format_datetime, format_scope
from app.ui.utils.mappers import (
    build_run_kpis,
    comparison_insights_for_case,
    extract_score_value,
    findings_table_rows,
    report_findings_count,
    score_interpretation,
    split_recommendation_sections,
)
from app.ui.utils.session_state import init_session_state, remember_finding_selection, remember_run_selection


def _list_runs_safe(client: APIClient, *, limit: int) -> list[dict]:
    try:
        return client.list_runs(limit=limit)
    except TypeError:
        return client.list_runs()


def _render_hypotheses(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay hipótesis generadas para este run.")
        return
    for item in items:
        attrs = item.get("attributes", {}) or {}
        st.markdown('<div class="rf20-narrative">', unsafe_allow_html=True)
        st.markdown(f"**{item.get('title') or item.get('id') or 'Hypothesis'}**")
        if item.get("subtitle"):
            st.caption(str(item.get("subtitle")))
        render_presentable_content(item.get("summary") or "Sin resumen.")
        st.caption(f"Tests candidatos: {', '.join(attrs.get('candidate_test_ids', [])) or '-'}")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_selected_tests(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay tests seleccionados.")
        return
    st.markdown('<div class="rf20-list">', unsafe_allow_html=True)
    for item in items:
        attrs = item.get("attributes") or {}
        st.markdown('<div class="rf20-list-item">', unsafe_allow_html=True)
        st.markdown(f"**{item.get('id') or '-'}**")
        if item.get("subtitle"):
            st.caption(str(item.get("subtitle")))
        render_presentable_content(item.get("summary") or "Sin motivo de selección detallado.")
        st.markdown(
            f"""
            <div class="rf20-meta-line">
                Origen: <span class="rf20-meta-inline">{item.get("status") or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Score: <span class="rf20-meta-inline">{attrs.get("score", "-")}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_planner_trace(detail: Dict[str, Any], items: List[Dict[str, Any]], *, planner: str) -> None:
    graph_meta = ((detail.get("metadata") or {}).get("graph_run_metadata") or {}) if isinstance(detail.get("metadata"), dict) else {}
    runtime = (graph_meta.get("llm_runtime_by_node") or {}) if isinstance(graph_meta, dict) else {}
    node_key = "hypothesis_planner" if planner == "hypothesis" else "test_planner"
    llm_call_status_key = "hypothesis_llm_call_status" if planner == "hypothesis" else "test_planner_llm_call_status"
    llm_status = graph_meta.get(llm_call_status_key)
    node_runtime = runtime.get(node_key, {}) if isinstance(runtime, dict) else {}
    sources = sorted({str(item.get("status") or "").strip() for item in items if str(item.get("status") or "").strip()})
    if not llm_status and not sources:
        return
    st.markdown(
        f"""
        <div class="rf20-callout tight" style="background:#F8FBFA; margin-bottom:0.8rem;">
            <div class="rf20-summary-label">Trazabilidad del planner</div>
            <div class="rf20-meta-line">
                Estado LLM: <span class="rf20-meta-inline">{llm_status or node_runtime.get("status") or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Modelo: <span class="rf20-meta-inline">{node_runtime.get("model_used") or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Salida mostrada: <span class="rf20-meta-inline">{", ".join(sources) or "-"}</span>
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
        attrs = item.get("attributes", {}) or {}
        rows.append(
            {
                "label": item.get("id"),
                "confidence": extract_score_value(item),
                "source": item.get("status"),
                "summary": item.get("summary"),
                "entities_scored": (attrs.get("summary", {}) or {}).get("entities_scored"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=240)
    for row in rows:
        if row.get("summary"):
            with st.expander(f"Ver detalle de score: {row.get('label')}", expanded=False):
                render_presentable_content(row["summary"])


def _render_comparison_insights(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay comparativas secundarias disponibles para este run.")
        return
    for item in items:
        attrs = item.get("attributes", {}) or {}
        runs_compared = attrs.get("runs_compared", []) or []
        common_tests = attrs.get("common_selected_tests", []) or []
        common_types = attrs.get("common_fraud_types_with_findings", []) or []
        st.markdown('<div class="rf20-recommendation">', unsafe_allow_html=True)
        st.markdown(f"**{item.get('title') or 'Insight comparativo'}**")
        if item.get("subtitle"):
            st.caption(str(item.get("subtitle")))
        render_presentable_content(item.get("summary") or "")
        st.markdown(
            f"""
            <div class="rf20-meta-line">
                Comparado contra: <span class="rf20-meta-inline">{", ".join(runs_compared) or "otros runs del análisis secundario"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Tests compartidos: <span class="rf20-meta-inline">{", ".join(common_tests) or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Tipologías coincidentes: <span class="rf20-meta-inline">{", ".join(common_types) or "-"}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    configure_page(page_title="Resultados")
    init_session_state()
    st.session_state["_active_page"] = "results"
    render_page_header(
        title="Resultados del análisis",
        subtitle="Abre el análisis actual, revisa el scoring principal y navega por hallazgos, explicación, comparativas y recomendaciones.",
    )

    client = APIClient()
    selected_run_id = st.session_state.selected_run_id
    runs: list[dict[str, Any]] = []
    if not selected_run_id:
        try:
            runs = _list_runs_safe(client, limit=20)
        except APIClientError as exc:
            st.error(f"No se pudo cargar el historial de runs: {exc}")
            return
        run_ids = [item["run_id"] for item in runs]
        selected_run_id = run_ids[0] if run_ids else None
        if not selected_run_id:
            st.info("Todavía no hay runs disponibles.")
            return
        st.session_state.selected_run_id = selected_run_id
    else:
        top_left_sel, top_right_sel = st.columns([3.2, 1.2], gap="large")
        with top_left_sel:
            st.caption(f"Análisis activo: `{selected_run_id}`")
        with top_right_sel:
            if st.button("Cambiar análisis", use_container_width=True):
                st.session_state.results_show_run_picker = not bool(st.session_state.get("results_show_run_picker", False))
        if st.session_state.get("results_show_run_picker", False):
            try:
                runs = _list_runs_safe(client, limit=20)
            except APIClientError as exc:
                st.error(f"No se pudo cargar el historial de runs: {exc}")
                return
            run_ids = [item["run_id"] for item in runs]
            if run_ids:
                picked = st.selectbox(
                    "Selecciona otro análisis",
                    run_ids,
                    index=run_ids.index(selected_run_id) if selected_run_id in run_ids else 0,
                )
                if picked != selected_run_id:
                    selected_run_id = picked
                    st.session_state.selected_run_id = picked
                    st.session_state.selected_graph_payload = None
                    st.rerun()

    try:
        detail = client.get_run(selected_run_id)
        graph = client.get_run_graph(selected_run_id)
        report = client.get_run_report(selected_run_id)
        remember_run_selection(run_id=selected_run_id, run_detail=detail)
        st.session_state.selected_graph_payload = graph
    except APIClientError as exc:
        st.error(f"No se pudieron cargar los resultados del run: {exc}")
        return

    findings_total = report_findings_count(report) or graph.get("counts", {}).get("findings", 0)
    scores = graph.get("scores", [])
    executive_summary = graph.get("executive_summary")
    score_value = "-"
    score_summary = "El scoring resume la señal final prioritaria del run."
    score_label = "-"
    score_numeric = None
    if scores:
        score_label = scores[0].get("title") or scores[0].get("id") or "-"
        maybe = extract_score_value(scores[0])
        if maybe is not None:
            score_numeric = maybe
            score_value = f"{maybe:.2f}"
        score_summary = scores[0].get("summary") or score_summary
    score_hint = score_interpretation(score_numeric)

    top_left, top_right = st.columns([4.6, 1.2], gap="large")
    with top_left:
        st.markdown(
            f"""
            <div class="rf20-callout">
                <div class="rf20-eyebrow">Análisis abierto ahora</div>
                <div class="rf20-title" style="font-size:1.4rem; margin-bottom:0.15rem;">{detail.get("run_id")}</div>
                <div class="rf20-subtitle">{detail.get("dataset_id") or "-"} · {format_scope(detail.get("scope"))} · {format_datetime(detail.get("created_at_utc"))}</div>
                <div class="rf20-summary-strip">
                    <div class="rf20-summary-item"><div class="rf20-summary-label">KB rebuild</div><div class="rf20-summary-value">{format_bool(detail.get("kb_index_enabled"))}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Graph status</div><div class="rf20-summary-value">{graph.get("graph_status") or "-"}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">KB index</div><div class="rf20-summary-value">{graph.get("kb_index_status") or "-"}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Findings reportados</div><div class="rf20-summary-value">{findings_total}</div></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with top_right:
        render_status_badge(detail.get("status"))
        st.markdown(
            f"""
            <div class="rf20-callout tight" style="margin-top:0.85rem;">
                <div class="rf20-summary-label">Score principal</div>
                <div style="font-size:2rem; font-weight:750; color:#0A5D57; line-height:1.05;">{score_value}</div>
                <div class="rf20-list-subtitle" style="margin-top:0.2rem;">{score_label}</div>
                <div class="rf20-mini-note" style="margin-top:0.35rem;">{score_hint["label"]}. {score_hint["summary"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if executive_summary:
        st.markdown('<div class="rf20-callout" style="margin-top:0.9rem; background:#F7FBFA;">', unsafe_allow_html=True)
        st.markdown("**Resumen ejecutivo del hallazgo**")
        render_presentable_content(executive_summary)
        st.markdown("</div>", unsafe_allow_html=True)

    render_result_kpis(build_run_kpis(graph), score_value=score_value)

    render_divider()
    render_section_heading(
        title="Lectura del análisis",
        subtitle="Empieza por la señal principal y profundiza después en hallazgos, scoring, narrativa y comparativas del second-level explainer.",
    )
    tab_hyp, tab_tests, tab_findings, tab_scores, tab_expl, tab_compare, tab_rec = st.tabs(
        ["Hypotheses", "Selected tests", "Findings", "Scores", "Explicación", "Comparativas", "Recomendaciones"]
    )

    with tab_hyp:
        _render_planner_trace(detail, graph.get("hypotheses", []), planner="hypothesis")
        _render_hypotheses(graph.get("hypotheses", []))
    with tab_tests:
        _render_planner_trace(detail, graph.get("selected_tests", []), planner="test")
        _render_selected_tests(graph.get("selected_tests", []))
    with tab_findings:
        render_section_heading(
            title="Hallazgos detectados",
            subtitle="Cada bloque corresponde a un test con sus hallazgos asociados. Abre el detalle para navegar entre todos los casos detectados por ese test.",
        )
        finding_rows = findings_table_rows(graph.get("findings", []))

        def _open_detail(row: dict) -> None:
            remember_finding_selection(finding_id=row.get("finding_id") or "", finding=row)
            st.switch_page("pages/4_Detalle_hallazgo.py")

        render_findings_list(finding_rows, on_select=_open_detail)
    with tab_scores:
        st.markdown(f"**{score_hint['label']}.** {score_hint['summary']}")
        st.caption("El score se calcula en el nodo de scoring a partir de findings agregados por entidad, tipologías detectadas y evidencia consolidada del run.")
        _render_scores(scores)
    with tab_expl:
        render_explanations_panel(graph.get("explanations", []))
    with tab_compare:
        render_section_heading(
            title="Comparativas del caso",
            subtitle="Se muestra contra qué runs y señales se ha contrastado este caso, qué desviación relevante aparece y por qué refuerza su revisión.",
        )
        _render_comparison_insights(comparison_insights_for_case(graph.get("comparison_insights", [])))
    with tab_rec:
        sections = split_recommendation_sections(graph.get("second_level_analysis", []))
        if executive_summary:
            st.markdown('<div class="rf20-callout tight" style="background:#F7FBFA; margin-bottom:0.8rem;">', unsafe_allow_html=True)
            st.markdown("**Resumen ejecutivo del hallazgo**")
            render_presentable_content(executive_summary)
            st.markdown("</div>", unsafe_allow_html=True)
        render_recommendations_panel(
            sections["recommendations"],
            title="Recomendaciones",
            empty_message="No hay recomendaciones específicas para este caso.",
        )
        render_recommendations_panel(
            sections["recommended_tests"],
            title="Tests recomendados",
            empty_message="No hay tests adicionales sugeridos por el second-level explainer.",
        )
        render_recommendations_panel(
            sections["audit_procedures"],
            title="Procedimiento auditor",
            empty_message="No hay procedimiento auditor adicional sugerido.",
        )

    with st.expander("Detalle técnico del run", expanded=False):
        st.write(
            {
                "graph_status": graph.get("graph_status"),
                "kb_index_status": graph.get("kb_index_status"),
                "report_overall_status": report.get("overall_status"),
                "artifact_keys": detail.get("artifact_keys", {}),
            }
        )

    if str(detail.get("status", "")).upper() in {"RUNNING", "SUBMITTED"}:
        st.info("Ejecución en curso. La pantalla se actualizará automáticamente cada 4 segundos mientras siga activa.")
        time.sleep(4)
        st.rerun()


if __name__ == "__main__":
    main()
