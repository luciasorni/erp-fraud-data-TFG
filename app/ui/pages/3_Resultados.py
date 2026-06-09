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


def _get_session_cached(cache_key: str, *, run_id: str, loader) -> dict:
    cache = st.session_state.setdefault(cache_key, {})
    if run_id not in cache:
        cache[run_id] = loader()
    return cache[run_id]


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


def _render_selected_tests(items: List[Dict[str, Any]], *, finding_rows: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay tests seleccionados.")
        return

    findings_by_test = {row.get("test_id"): row for row in finding_rows if row.get("test_id")}

    for item in items:
        attrs = item.get("attributes") or {}
        test_id = str(item.get("id") or "").strip()
        finding_row = findings_by_test.get(test_id, {})
        hypothesis_id = attrs.get("hypothesis_id") or item.get("subtitle")
        fraud_type = attrs.get("fraud_type")
        process_step = attrs.get("process_step") or finding_row.get("process_step")
        execution_status = finding_row.get("status")
        with st.container(border=True):
            st.markdown(f"#### {test_id or '-'}")
            caption_bits = [bit for bit in [hypothesis_id, fraud_type] if bit]
            if caption_bits:
                st.caption(" · ".join(map(str, caption_bits)))

            render_presentable_content(item.get("summary") or "Sin motivo de selección detallado.")

            meta_cols = st.columns(3, gap="small")
            with meta_cols[0]:
                st.caption("Origen")
                st.markdown(f"**{item.get('status') or '-'}**")
            with meta_cols[1]:
                st.caption("Estado en ejecución")
                st.markdown(f"**{execution_status or 'Pendiente o no visible en este run'}**")
            with meta_cols[2]:
                st.caption("Hypothesis")
                st.markdown(f"**{hypothesis_id or 'No disponible en este run'}**")

            if process_step:
                st.caption(f"Paso afectado: {process_step}")

            if finding_row.get("error_summary"):
                st.caption(str(finding_row.get("error_summary")))


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


def _build_result_kpi_help_texts(
    *,
    graph: Dict[str, Any],
    finding_rows: List[Dict[str, Any]],
    score_label: str,
    score_hint: Dict[str, str],
) -> Dict[str, str]:
    hypothesis_types: list[str] = []
    for item in graph.get("hypotheses", []):
        attrs = item.get("attributes", {}) or {}
        fraud_type = str(attrs.get("fraud_type") or item.get("subtitle") or "").strip()
        if fraud_type and fraud_type not in hypothesis_types:
            hypothesis_types.append(fraud_type)

    skipped_count = sum(1 for row in finding_rows if str(row.get("status", "")).upper() == "SKIPPED")
    tests_with_findings = sum(1 for row in finding_rows if int(row.get("finding_count", 0) or 0) > 0)
    total_hallazgos = sum(int(row.get("finding_count", 0) or 0) for row in finding_rows)

    help_texts = {
        "hypotheses": (
            f"Tipologías activas: {', '.join(hypothesis_types[:3])}."
            if hypothesis_types
            else "No hay tipologías explícitas en las hipótesis de este run."
        ),
        "selected_tests": (
            f"{tests_with_findings} test(s) con hallazgos y {skipped_count} marcado(s) como skipped."
            if finding_rows
            else "No hay ejecución visible de tests para este run."
        ),
        "findings": (
            f"{total_hallazgos} hallazgo(s) agregados en {tests_with_findings} test(s) con señal."
            if finding_rows
            else "No hay hallazgos visibles en este run."
        ),
        "score": (
            f"{score_label or 'Sin etiqueta'} · {score_hint['label'].lower()}."
            if score_label and score_label != "-"
            else score_hint["summary"]
        ),
    }
    return help_texts


def _render_comparison_insights(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.info("No hay comparativas secundarias disponibles para este run.")
        return

    for item in items:
        attrs = item.get("attributes", {}) or {}
        runs_compared = attrs.get("runs_compared", []) or []
        evidence = attrs.get("evidence", []) or []
        implication = attrs.get("implication")
        recommendation = attrs.get("recommendation")
        section = attrs.get("section") or "-"

        with st.container(border=True):
            st.markdown(f"#### {item.get('title') or 'Insight comparativo'}")
            if item.get("subtitle"):
                st.caption(str(item.get("subtitle")))

            render_presentable_content(item.get("summary") or "")

            if implication:
                st.markdown("**Por qué importa**")
                render_presentable_content(implication)
            if recommendation:
                st.markdown("**Qué refuerza o sugiere**")
                render_presentable_content(recommendation)
            if evidence:
                st.markdown("**Evidencia de comparación**")
                render_presentable_content(evidence)

            st.caption(
                f"Sección: {section} · Runs comparados: {', '.join(runs_compared) or 'sin runs relacionados'}"
            )


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
        detail = _get_session_cached("run_detail_cache", run_id=selected_run_id, loader=lambda: client.get_run(selected_run_id))
        graph = _get_session_cached("run_graph_cache", run_id=selected_run_id, loader=lambda: client.get_run_graph(selected_run_id))
        remember_run_selection(run_id=selected_run_id, run_detail=detail)
        st.session_state.selected_graph_payload = graph
    except APIClientError as exc:
        st.error(f"No se pudieron cargar los resultados del run: {exc}")
        return

    finding_rows = findings_table_rows(
        graph.get("findings", []),
        selected_tests=graph.get("selected_tests", []),
        explanations=graph.get("explanations", []),
    )
    findings_total = sum(int(row.get("finding_count", 0) or 0) for row in finding_rows) or graph.get("counts", {}).get("findings", 0)
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
    render_result_kpis(
        build_run_kpis(graph),
        score_value=score_value,
        help_texts=_build_result_kpi_help_texts(
            graph=graph,
            finding_rows=finding_rows,
            score_label=score_label,
            score_hint=score_hint,
        ),
    )

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
        _render_selected_tests(graph.get("selected_tests", []), finding_rows=finding_rows)

    with tab_findings:
        render_section_heading(
            title="Hallazgos detectados",
            subtitle="Cada bloque corresponde a un test con sus hallazgos asociados. Abre el detalle para navegar entre todos los casos detectados por ese test.",
        )

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
        render_explanations_panel(
            graph.get("explanations", []),
            findings=graph.get("findings", []),
            selected_tests=graph.get("selected_tests", []),
        )

    with tab_compare:
        render_section_heading(
            title="Comparativas del caso",
            subtitle="Se muestra contra qué runs y señales se ha contrastado este caso, qué desviación relevante aparece y por qué refuerza su revisión.",
        )
        _render_comparison_insights(comparison_insights_for_case(graph.get("comparison_insights", [])))

    with tab_rec:
        sections = split_recommendation_sections(graph.get("second_level_analysis", []))

        st.subheader("Acciones recomendadas")
        render_recommendations_panel(
            sections["recommendations"],
            title="Recomendaciones globales del run",
            empty_message="No hay acciones recomendadas para este run.",
        )
        st.divider()

        st.subheader("Tests sugeridos")
        render_recommendations_panel(
            sections["recommended_tests"],
            title="Tests recomendados",
            empty_message="No hay tests sugeridos para este run.",
        )
        st.divider()

        st.subheader("Procedimiento auditor")
        render_recommendations_panel(
            sections["audit_procedures"],
            title="Procedimiento auditor",
            empty_message="No hay procedimiento auditor para este run.",
        )

    with st.expander("Detalle técnico del run", expanded=False):
        try:
            report = _get_session_cached("run_report_cache", run_id=selected_run_id, loader=lambda: client.get_run_report(selected_run_id))
        except APIClientError as exc:
            st.warning(f"No se pudo cargar `report.json`: {exc}")
            report = {}
        st.write(
            {
                "graph_status": graph.get("graph_status"),
                "kb_index_status": graph.get("kb_index_status"),
                "report_overall_status": report.get("overall_status") if isinstance(report, dict) else None,
                "artifact_keys": detail.get("artifact_keys", {}),
            }
        )

    if str(detail.get("status", "")).upper() in {"RUNNING", "SUBMITTED"}:
        st.info("Ejecución en curso. La pantalla se actualizará automáticamente cada 4 segundos mientras siga activa.")
        time.sleep(4)
        st.rerun()


if __name__ == "__main__":
    main()
