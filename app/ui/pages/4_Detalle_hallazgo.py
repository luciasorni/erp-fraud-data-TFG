from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui.components.drilldown_table import render_drilldown_table
from app.ui.components.explanations_panel import render_explanations_panel
from app.ui.components.findings_detail import render_finding_detail
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


def _list_runs_safe(client: APIClient, *, limit: int) -> list[dict]:
    try:
        return client.list_runs(limit=limit)
    except TypeError:
        return client.list_runs()


def _execute_drilldown_direct(
    client: APIClient,
    *,
    run_id: str,
    action: str,
    test_id: str,
    keys: dict,
    query_id: str | None,
    limit_rows: int,
    order_direction: str,
) -> dict | None:
    with st.status("Recuperando evidencia detallada...", expanded=True) as status:
        try:
            status.write("Ejecutando drilldown directo contra el backend...")
            result = client.post_drilldown(
                run_id=run_id,
                action=action,
                test_id=test_id,
                keys=keys,
                query_id=query_id,
                limit_rows=limit_rows,
                order_direction=order_direction,
            )
            status.update(label="Drilldown listo", state="complete", expanded=False)
            return result
        except APIClientError as exc:
            status.update(label="Fallo en drilldown", state="error", expanded=True)
            st.error(f"No se pudo ejecutar el drilldown: {exc}")
            return None


def _build_context_marker(
    *,
    run_id: str,
    test_id: str,
    selected_row: dict | None,
    evidence_keys: dict,
) -> str:
    entity_key = ""
    if selected_row:
        entity_key = str(selected_row.get("entity_key") or "").strip()
    keys_repr = "|".join(f"{k}={v}" for k, v in sorted((evidence_keys or {}).items()))
    return f"{run_id}::{test_id}::{entity_key}::{keys_repr}"


def main() -> None:
    configure_page(page_title="Detalle del hallazgo")
    init_session_state()
    st.session_state["_active_page"] = "finding_detail"

    render_page_header(
        title="Detalle del hallazgo",
        subtitle="Investiga el caso con una lectura guiada: resumen ejecutivo, narrativa, comparativas, recomendaciones y drilldown.",
    )

    client = APIClient()
    run_id = st.session_state.selected_run_id
    finding = st.session_state.selected_finding
    graph = st.session_state.selected_graph_payload

    selected_run_id = run_id
    runs: list[dict] = []

    if not selected_run_id:
        try:
            runs = _list_runs_safe(client, limit=20)
        except APIClientError as exc:
            st.error(f"No se pudo cargar el historial de runs: {exc}")
            return

        run_ids = [item["run_id"] for item in runs]
        if not run_ids:
            st.info("Todavía no hay runs disponibles.")
            return

        selected_run_id = run_ids[0]
        st.session_state.selected_run_id = selected_run_id
    else:
        top_left_sel, top_right_sel = st.columns([3.2, 1.2], gap="large")
        with top_left_sel:
            st.caption(f"Run activo: `{selected_run_id}`")
        with top_right_sel:
            if st.button("Cambiar run", use_container_width=True):
                st.session_state.detail_show_run_picker = not bool(
                    st.session_state.get("detail_show_run_picker", False)
                )

        if st.session_state.get("detail_show_run_picker", False):
            try:
                runs = _list_runs_safe(client, limit=20)
            except APIClientError as exc:
                st.error(f"No se pudo cargar el historial de runs: {exc}")
                return

            run_ids = [item["run_id"] for item in runs]
            if run_ids:
                picked = st.selectbox(
                    "Selecciona otro run",
                    run_ids,
                    index=run_ids.index(selected_run_id) if selected_run_id in run_ids else 0,
                )
                if picked != selected_run_id:
                    st.session_state.selected_run_id = picked
                    st.session_state.selected_finding = None
                    st.session_state.selected_finding_id = None
                    st.session_state.selected_finding_row_key = None
                    st.session_state.selected_graph_payload = None
                    st.session_state.drilldown_result = None
                    st.session_state.drilldown_context_marker = None
                    st.rerun()

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

    finding_options: list[str] = []
    finding_by_label: dict[str, dict] = {}

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

        selector_labels: list[str] = []
        key_to_row: dict[str, dict] = {}

        for index, row in enumerate(finding_rows, start=1):
            entity_key = str(row.get("entity_key", "")).strip() or f"hallazgo-{index}"
            keys = row.get("keys", {}) if isinstance(row.get("keys"), dict) else {}
            key_preview = ", ".join(f"{k}={v}" for k, v in list(keys.items())[:2])
            label = f"{index}. {entity_key}" if not key_preview else f"{index}. {entity_key} · {key_preview}"
            selector_labels.append(label)
            key_to_row[label] = row

        current_label = (
            st.session_state.selected_finding_row_key
            if st.session_state.selected_finding_row_key in selector_labels
            else selector_labels[0]
        )
        selected_label = st.selectbox(
            "Hallazgo a inspeccionar",
            selector_labels,
            index=selector_labels.index(current_label),
        )
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
    executive_summary = graph.get("executive_summary")
    rec_sections = split_recommendation_sections(recommendations)

    render_section_heading(
        title="Resumen ejecutivo del hallazgo",
        subtitle="Narrativa principal del caso: por qué se detectó, qué evidencia lo respalda y por qué merece revisión.",
    )
    if executive_summary:
        st.markdown(
            '<div class="rf20-callout tight" style="background:#F7FBFA; margin-bottom:0.8rem;">',
            unsafe_allow_html=True,
        )
        st.markdown("**Lectura ejecutiva**")
        render_presentable_content(executive_summary)
        st.markdown("</div>", unsafe_allow_html=True)

    render_explanations_panel([explanation] if explanation else [])

    render_divider()
    render_section_heading(
        title="Evidencia principal",
        subtitle="Claves de negocio destacadas para orientar la investigación antes de ir al drilldown.",
    )

    evidence_keys = {}
    selected_query_id = None
    drilldown_error = None
    required_keys = []
    missing_keys = []

    if selected_row and isinstance(selected_row.get("keys"), dict):
        evidence_keys = selected_row.get("keys") or {}
        selected_query_id = selected_row.get("query_id")
        drilldown_error = selected_row.get("drilldown_error")
        required_keys = selected_row.get("required_keys") or []
        missing_keys = selected_row.get("missing_keys") or []
    elif finding and finding.get("sample_keys"):
        evidence_keys = finding.get("sample_keys") or {}
        selected_query_id = finding.get("sample_query_id")
        drilldown_error = finding.get("drilldown_error")
        required_keys = finding.get("required_keys") or []
        missing_keys = finding.get("missing_keys") or []

    context_marker = _build_context_marker(
        run_id=run_id,
        test_id=str(finding.get("test_id") or ""),
        selected_row=selected_row,
        evidence_keys=evidence_keys,
    )
    if st.session_state.get("drilldown_context_marker") != context_marker:
        st.session_state.drilldown_result = None
        st.session_state.drilldown_context_marker = context_marker

    if evidence_keys:
        st.table([{"campo": key, "valor": value} for key, value in evidence_keys.items()])
    else:
        st.info("No hay claves de evidencia disponibles para este hallazgo.")

    st.markdown(
        f"""
        <div class="rf20-callout tight" style="margin-top:0.8rem;">
            <div class="rf20-summary-label">Contexto de drilldown</div>
            <div class="rf20-meta-line">
                Test: <span class="rf20-meta-inline">{finding.get("test_id") or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Query: <span class="rf20-meta-inline">{selected_query_id or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Keys requeridas: <span class="rf20-meta-inline">{", ".join(required_keys) or "-"}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if missing_keys:
        st.warning(f"El hallazgo no es drilldownable todavía. Faltan keys mínimas: {missing_keys}")
    elif drilldown_error:
        st.warning(str(drilldown_error))

    render_divider()
    render_section_heading(
        title="Por qué este hallazgo destaca",
        subtitle="Comparativas, recomendaciones y pasos de revisión agrupados para leer el caso de forma más clara.",
    )

    tab_labels = ["Comparativas", "Recomendaciones", "Tests", "Procedimiento auditor"]
    tab_comparisons, tab_recommendations, tab_tests, tab_audit = st.tabs(tab_labels)

    with tab_comparisons:
        render_recommendations_panel(
            comparisons,
            title="Comparativas relevantes",
            empty_message="No hay comparativas relevantes disponibles.",
        )

    with tab_recommendations:
        render_recommendations_panel(
            rec_sections["recommendations"],
            title="Recomendaciones",
            empty_message="No hay recomendaciones específicas para este hallazgo.",
        )

    with tab_tests:
        render_recommendations_panel(
            rec_sections["recommended_tests"],
            title="Tests recomendados",
            empty_message="No hay tests adicionales sugeridos para este hallazgo.",
        )

    with tab_audit:
        render_recommendations_panel(
            rec_sections["audit_procedures"],
            title="Procedimiento auditor",
            empty_message="No hay procedimiento auditor adicional sugerido.",
        )

    render_divider()
    render_section_heading(
        title="Drilldown",
        subtitle="Ejecuta la recuperación de evidencia detallada a partir de las claves del hallazgo.",
    )

    drilldown_ready = bool(evidence_keys) and not bool(missing_keys) and not bool(drilldown_error)
    if not drilldown_ready:
        st.info("Este hallazgo no dispone de contexto suficiente para ejecutar drilldown.")
        render_drilldown_table(st.session_state.drilldown_result)
        return

    controls = st.columns([1.15, 0.95, 0.95, 1.25])
    action = controls[0].selectbox("Acción", ALLOWED_DRILLDOWN_ACTIONS)
    limit_rows = controls[1].slider("Límite", min_value=10, max_value=200, value=50, step=10)
    order_direction = controls[2].selectbox("Orden", ["ASC", "DESC"])

    if controls[3].button("Ejecutar drilldown", type="primary", use_container_width=True):
        result = _execute_drilldown_direct(
            client,
            run_id=run_id,
            action=action,
            test_id=finding.get("test_id") or "",
            keys=evidence_keys,
            query_id=selected_query_id,
            limit_rows=limit_rows,
            order_direction=order_direction,
        )
        if result:
            st.session_state.drilldown_result = result
            st.success("Evidencia de drilldown lista.")

    render_drilldown_table(st.session_state.drilldown_result)


if __name__ == "__main__":
    main()