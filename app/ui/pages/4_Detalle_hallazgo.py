from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from app.ui.components.drilldown_table import render_drilldown_table
from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_detail import render_finding_detail
from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
from app.ui.components.recommendations_panel import render_recommendations_panel
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.constants import ALLOWED_DRILLDOWN_ACTIONS
from app.ui.utils.mappers import (
    comparison_insights_for_case,
    explanation_for_test,
    findings_table_rows,
    recommendations_for_finding,
    split_recommendation_sections,
)
from app.ui.utils.session_state import init_session_state


def _poll_drilldown_job(client: APIClient, *, run_id: str, job_id: str) -> dict | None:
    with st.status("Recuperando evidencia detallada...", expanded=True) as status:
        started = time.time()
        last_message = ""
        while time.time() - started < 180:
            payload = client.get_drilldown_job(run_id=run_id, job_id=job_id)
            message = f"{payload.get('stage', '').capitalize()}: {payload.get('message', '')}"
            if message != last_message:
                status.write(message)
                last_message = message
            if payload.get("status") == "SUCCEEDED":
                status.update(label="Drilldown listo", state="complete", expanded=False)
                return payload.get("result")
            if payload.get("status") == "FAILED":
                status.update(label="Fallo en drilldown", state="error", expanded=True)
                st.error(payload.get("error") or "No se pudo ejecutar el drilldown.")
                return None
            time.sleep(1.0)
        status.update(label="Timeout esperando el drilldown", state="error", expanded=True)
        st.error("El drilldown está tardando demasiado. Reintenta o revisa el backend.")
        return None


def main() -> None:
    configure_page(page_title="Detalle del hallazgo")
    init_session_state()
    render_page_header(
        title="Detalle del hallazgo",
        subtitle="Investiga el caso con una lectura guiada: resumen ejecutivo, narrativa, comparativas, recomendaciones y drilldown.",
    )

    client = APIClient()
    run_id = st.session_state.selected_run_id
    finding = st.session_state.selected_finding
    graph = st.session_state.selected_graph_payload

    runs = []
    try:
        runs = client.list_runs()
    except APIClientError as exc:
        st.error(f"No se pudo cargar el historial de runs: {exc}")
        return
    run_ids = [item["run_id"] for item in runs]
    if not run_ids:
        st.info("Todavía no hay runs disponibles.")
        return
    current_run_id = run_id if run_id in run_ids else run_ids[0]
    selected_run_id = st.selectbox(
        "Run a inspeccionar",
        run_ids,
        index=run_ids.index(current_run_id) if current_run_id in run_ids else 0,
    )
    if selected_run_id != st.session_state.selected_run_id:
        st.session_state.selected_run_id = selected_run_id
        st.session_state.selected_finding = None
        st.session_state.selected_finding_id = None
        st.session_state.selected_finding_row_key = None
        st.session_state.drilldown_result = None
    run_id = selected_run_id
    if not graph or str(graph.get("run_id") or "").strip() != selected_run_id:
        try:
            graph = client.get_run_graph(run_id)
            st.session_state.selected_graph_payload = graph
        except APIClientError as exc:
            st.error(f"No se pudo cargar el contexto de resultados del run: {exc}")
            return

    findings_available = [
        row for row in findings_table_rows(graph.get("findings", [])) if isinstance(row, dict)
    ]
    if not findings_available:
        st.info("Este run no tiene hallazgos disponibles para inspección.")
        return
    finding_options = []
    finding_by_label = {}
    for item in findings_available:
        label = (
            f"{item.get('test_id') or item.get('finding_id')} · "
            f"{item.get('fraud_type') or '-'} · "
            f"{item.get('finding_count') or 0} hallazgos"
        )
        finding_options.append(label)
        finding_by_label[label] = item
    default_finding = finding if finding in findings_available else None
    default_label = None
    if default_finding:
        for label, item in finding_by_label.items():
            if item.get("test_id") == default_finding.get("test_id"):
                default_label = label
                break
    chosen_label = st.selectbox(
        "Test/hallazgo a inspeccionar",
        finding_options,
        index=finding_options.index(default_label) if default_label in finding_options else 0,
    )
    finding = finding_by_label[chosen_label]
    st.session_state.selected_finding = finding
    st.session_state.selected_finding_id = finding.get("finding_id")

    render_finding_detail(finding)

    finding_rows = finding.get("rows", []) if finding else []
    selected_row = None
    if finding_rows:
        st.markdown(
            f"""
            <div class="rf20-callout tight" style="margin-bottom:0.8rem;">
                <div class="rf20-summary-label">Hallazgos disponibles</div>
                <div class="rf20-meta-line" style="font-size:0.95rem; color:#12302B;">
                    Este test tiene {len(finding_rows)} hallazgos. Selecciona cuál quieres inspeccionar y usar para drilldown.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selector_labels = []
        key_to_row = {}
        for index, row in enumerate(finding_rows, start=1):
            entity_key = str(row.get("entity_key", "")).strip() or f"hallazgo-{index}"
            keys = row.get("keys", {}) if isinstance(row.get("keys"), dict) else {}
            key_preview = ", ".join(f"{k}={v}" for k, v in list(keys.items())[:2])
            label = f"{index}. {entity_key}" if not key_preview else f"{index}. {entity_key} · {key_preview}"
            selector_labels.append(label)
            key_to_row[label] = row
        current_label = st.session_state.selected_finding_row_key if st.session_state.selected_finding_row_key in selector_labels else selector_labels[0]
        selected_label = st.selectbox("Hallazgo a inspeccionar", selector_labels, index=selector_labels.index(current_label))
        st.session_state.selected_finding_row_key = selected_label
        selected_row = key_to_row[selected_label]
        overview_rows = []
        for index, row in enumerate(finding_rows, start=1):
            keys = row.get("keys", {}) if isinstance(row.get("keys"), dict) else {}
            overview_rows.append(
                {
                    "hallazgo": index,
                    "entity_key": row.get("entity_key") or "-",
                    "claves": ", ".join(f"{k}={v}" for k, v in list(keys.items())[:3]) or "-",
                }
            )
        with st.expander("Ver todos los hallazgos detectados", expanded=True):
            st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)

    explanation = explanation_for_test(graph.get("explanations", []), finding.get("test_id") if finding else None)
    recommendations = recommendations_for_finding(graph.get("second_level_analysis", []))
    comparisons = comparison_insights_for_case(graph.get("comparison_insights", []))
    executive_summary = str(graph.get("executive_summary") or "").strip()
    rec_sections = split_recommendation_sections(recommendations)

    render_section_heading(
        title="Resumen ejecutivo del hallazgo",
        subtitle="Narrativa principal del caso: por qué se detectó, qué evidencia lo respalda y por qué merece revisión.",
    )
    if executive_summary:
        st.markdown(
            f"""
            <div class="rf20-callout tight" style="background:#F7FBFA; margin-bottom:0.8rem;">
                <div class="rf20-summary-label">Lectura ejecutiva</div>
                <div class="rf20-meta-line" style="font-size:0.95rem; color:#12302B;">{executive_summary}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    render_explanations_panel([explanation] if explanation else [])

    render_divider()
    render_section_heading(
        title="Evidencia principal",
        subtitle="Claves de negocio destacadas para orientar la investigación antes de ir al drilldown.",
    )
    evidence_keys = {}
    if selected_row and isinstance(selected_row.get("keys"), dict):
        evidence_keys = selected_row.get("keys") or {}
    elif finding and finding.get("sample_keys"):
        evidence_keys = finding.get("sample_keys") or {}
    if evidence_keys:
        st.table([{"campo": key, "valor": value} for key, value in evidence_keys.items()])
    else:
        st.info("No hay claves de evidencia disponibles para este hallazgo.")

    if comparisons:
        render_divider()
        render_section_heading(
            title="Por qué este caso destaca",
            subtitle="Insights comparativos del second-level explainer para contextualizar el caso frente al patrón esperado o frente a otros runs.",
        )
        render_recommendations_panel(
            comparisons,
            title="Comparativas relevantes",
            empty_message="No hay comparativas relevantes disponibles.",
        )

    render_divider()
    render_section_heading(
        title="Recomendaciones",
        subtitle="Siguientes pasos sugeridos para investigación, contraste adicional y validación.",
    )
    render_recommendations_panel(
        rec_sections["recommendations"],
        title="Recomendaciones",
        empty_message="No hay recomendaciones específicas para este hallazgo.",
    )
    render_recommendations_panel(
        rec_sections["recommended_tests"],
        title="Tests recomendados",
        empty_message="No hay tests adicionales sugeridos para este hallazgo.",
    )
    render_recommendations_panel(
        rec_sections["audit_procedures"],
        title="Procedimiento auditor",
        empty_message="No hay procedimiento auditor adicional sugerido.",
    )

    render_divider()
    render_section_heading(
        title="Drilldown",
        subtitle="Ejecuta la recuperación de evidencia detallada a partir de las claves del hallazgo. La operación puede tardar y se mostrará progreso real.",
    )
    if not finding or not finding.get("sample_keys"):
        if not evidence_keys:
            st.info("Este hallazgo no dispone de claves mínimas para ejecutar drilldown.")
            return

    controls = st.columns([1.15, 0.95, 0.95, 1.25])
    action = controls[0].selectbox("Acción", ALLOWED_DRILLDOWN_ACTIONS)
    limit_rows = controls[1].slider("Límite", min_value=10, max_value=200, value=50, step=10)
    order_direction = controls[2].selectbox("Orden", ["ASC", "DESC"])
    if controls[3].button("Ejecutar drilldown", type="primary", use_container_width=True):
        try:
            job = client.start_drilldown_job(
                run_id=run_id,
                action=action,
                test_id=finding.get("test_id") or "",
                keys=evidence_keys,
                limit_rows=limit_rows,
                order_direction=order_direction,
            )
            result = _poll_drilldown_job(client, run_id=run_id, job_id=job["job_id"])
            if result:
                st.session_state.drilldown_result = result
                st.success("Evidencia de drilldown lista.")
        except APIClientError as exc:
            st.error(f"No se pudo iniciar el drilldown: {exc}")

    render_drilldown_table(st.session_state.drilldown_result)


if __name__ == "__main__":
    main()
