from __future__ import annotations

import time
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_list import render_findings_list
from app.ui.components.header import (
    configure_page,
    render_divider,
    render_page_header,
    render_section_heading,
)
from app.ui.components.recommendations_panel import (
    render_presentable_content,
    render_recommendations_panel,
)
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
from app.ui.utils.session_state import (
    init_session_state,
    remember_finding_selection,
    remember_run_selection,
)


def _list_runs_safe(client: APIClient, *, limit: int) -> list[dict]:
    try:
        return client.list_runs(limit=limit)
    except TypeError:
        return client.list_runs()


def _render_run_overview(detail: Dict[str, Any], graph: Dict[str, Any], findings_total: int, score_value: str, score_hint: Dict[str, str], score_label: str) -> None:
    left, right = st.columns([4.4, 1.3], gap="large")

    with left:
        with st.container(border=True):
            st.caption("ANÁLISIS ABIERTO")
            st.markdown(f"### `{detail.get('run_id')}`")
            st.write(
                f"{detail.get('dataset_id') or '-'} · "
                f"{format_scope(detail.get('scope'))} · "
                f"{format_datetime(detail.get('created_at_utc'))}"
            )

            meta_cols = st.columns(4, gap="small")
            meta_items = [
                ("KB rebuild", format_bool(detail.get("kb_index_enabled"))),
                ("Graph status", graph.get("graph_status") or "-"),
                ("KB index", graph.get("kb_index_status") or "-"),
                ("Findings", findings_total),
            ]
            for col, (label, value) in zip(meta_cols, meta_items):
                with col:
                    st.caption(label)
                    st.markdown(f"**{value}**")

    with right:
        render_status_badge(detail.get("status"))
        with st.container(border=True):
            st.caption("SCORE PRINCIPAL")
            st.markdown(f"## {score_value}")
            st.write(score_label or "-")
            st.caption(f"{score_hint['label']}. {score_hint['summary']}")


def _render_executive_summary(executive_summary: Any) -> None:
    if not executive_summary:
        return

    render_section_heading(
        title="Resumen ejecutivo del análisis",
        subtitle="Lectura principal del run: señal detectada, solidez de la evidencia y contexto para interpretar el resultado.",
    )

    if isinstance(executive_summary, dict):
        overall_assessment = executive_summary.get("overall_assessment")
        risk_posture = executive_summary.get("risk_posture")
        key_observations = executive_summary.get("key_observations") or []

        with st.container(border=True):
            st.markdown("#### Lectura ejecutiva")

            if overall_assessment:
                st.markdown("**Valoración general**")
                st.write(str(overall_assessment))

            if risk_posture:
                st.markdown("**Postura de riesgo**")
                st.write(str(risk_posture))

            if key_observations:
                st.markdown("**Observaciones clave**")
                for item in key_observations:
                    st.markdown(f"- {item}")

            remaining = {
                k: v
                for k, v in executive_summary.items()
                if k not in {"overall_assessment", "risk_posture", "key_observations"}
                and v not in (None, "", [], {})
            }
            if remaining:
                st.markdown("**Contexto adicional**")
                render_presentable_content(remaining)
    else:
        with st.container(border=True):
            st.markdown("#### Lectura ejecutiva")
            render_presentable_content(executive_summary)


def _render_hypotheses(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay hipótesis generadas para este run.")
        return

    for item in items:
        attrs = item.get("attributes", {}) or {}
        fraud_type = attrs.get("fraud_type") or item.get("subtitle") or "-"
        candidate_tests = attrs.get("candidate_test_ids", []) or []

        with st.container(border=True):
            st.markdown(f"#### {item.get('title') or item.get('id') or 'Hypothesis'}")
            st.caption(str(fraud_type))
            render_presentable_content(item.get("summary") or "Sin resumen.")
            if candidate_tests:
                st.caption(f"Tests candidatos: {', '.join(candidate_tests)}")


def _render_selected_tests(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay tests seleccionados.")
        return

    for item in items:
        attrs = item.get("attributes") or {}
        with st.container(border=True):
            st.markdown(f"#### {item.get('id') or '-'}")
            if item.get("subtitle"):
                st.caption(str(item.get("subtitle")))

            render_presentable_content(item.get("summary") or "Sin motivo de selección detallado.")

            meta_cols = st.columns(3, gap="small")
            with meta_cols[0]:
                st.caption("Origen")
                st.markdown(f"**{item.get('status') or '-'}**")
            with meta_cols[1]:
                st.caption("Score")
                st.markdown(f"**{attrs.get('score', '-')}**")
            with meta_cols[2]:
                st.caption("Hypothesis")
                st.markdown(f"**{attrs.get('hypothesis_id', '-') if attrs else '-'}**")


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

    with st.container(border=True):
        st.caption("TRAZABILIDAD DEL PLANNER")
        st.write(
            f"Estado LLM: **{llm_status or node_runtime.get('status') or '-'}**"
            f"  ·  Modelo: **{node_runtime.get('model_used') or '-'}**"
            f"  ·  Salida mostrada: **{', '.join(sources) or '-'}**"
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
                "entities_scored": (attrs.get("summary", {}) or {}).get("entities_scored"),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=240)

    for item in items:
        if item.get("summary"):
            with st.expander(f"Ver detalle de score: {item.get('title') or item.get('id')}", expanded=False):
                render_presentable_content(item["summary"])


def _render_comparison_insights(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay comparativas secundarias disponibles para este run.")
        return

    for item in items:
        attrs = item.get("attributes", {}) or {}
        runs_compared = attrs.get("runs_compared", []) or []
        common_tests = attrs.get("common_selected_tests", []) or []
        common_types = attrs.get("common_fraud_types_with_findings", []) or []

        with st.container(border=True):
            st.markdown(f"#### {item.get('title') or 'Insight comparativo'}")
            if item.get("subtitle"):
                st.caption(str(item.get("subtitle")))

            render_presentable_content(item.get("summary") or "")

            st.caption(
                f"Comparado contra: {', '.join(runs_compared) or 'otros runs del análisis secundario'}"
            )
            st.caption(f"Tests compartidos: {', '.join(common_tests) or '-'}")
            st.caption(f"Tipologías coincidentes: {', '.join(common_types) or '-'}")


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
                st.session_state.results_show_run_picker = not bool(
                    st.session_state.get("results_show_run_picker", False)
                )

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
    score_label = "-"
    score_numeric = None

    if scores:
        score_label = scores[0].get("title") or scores[0].get("id") or "-"
        maybe = extract_score_value(scores[0])
        if maybe is not None:
            score_numeric = maybe
            score_value = f"{maybe:.2f}"

    score_hint = score_interpretation(score_numeric)

    _render_run_overview(
        detail=detail,
        graph=graph,
        findings_total=findings_total,
        score_value=score_value,
        score_hint=score_hint,
        score_label=score_label,
    )

    render_divider()
    _render_executive_summary(executive_summary)

    render_divider()
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
        st.caption(
            "El score se calcula en el nodo de scoring a partir de findings agregados por entidad, tipologías detectadas y evidencia consolidada del run."
        )
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