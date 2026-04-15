from __future__ import annotations

import streamlit as st

from app.ui.components.dataset_summary import render_dataset_summary
from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.constants import LLM_OPTIONS, SCOPE_LABELS, SCOPE_OPTIONS
from app.ui.utils.formatters import format_bool, format_scope
from app.ui.utils.session_state import init_session_state, remember_last_run_response


STEP_DATASET = 1
STEP_CONFIG = 2
STEP_CONFIRM = 3


def _render_step_nav(current_step: int) -> None:
    labels = {
        STEP_DATASET: "1. Dataset",
        STEP_CONFIG: "2. Configuración",
        STEP_CONFIRM: "3. Confirmación",
    }
    html = ['<div class="rf20-stepnav">']
    for step, label in labels.items():
        state = "active" if step == current_step else "done" if step < current_step else ""
        html.append(f'<span class="rf20-stepchip {state}">{label}</span>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _load_selected_dataset(client: APIClient, dataset_id: str | None) -> dict | None:
    if not dataset_id:
        return None
    try:
        return client.get_dataset(dataset_id)
    except APIClientError as exc:
        st.error(f"No se pudo cargar el detalle del dataset: {exc}")
        return None


def main() -> None:
    configure_page(page_title="Nuevo análisis")
    init_session_state()
    render_page_header(
        title="Nuevo análisis antifraude ERP",
        subtitle="Sigue un flujo guiado para registrar el ERP, definir el alcance del análisis y lanzar la ejecución cloud.",
    )

    client = APIClient()
    step = st.session_state.get("analysis_step", STEP_DATASET)
    st.session_state.analysis_step = step

    datasets = []
    try:
        datasets = client.list_datasets()
    except APIClientError as exc:
        st.error(f"No se pudieron cargar los datasets: {exc}")

    _render_step_nav(step)

    if step == STEP_DATASET:
        render_section_heading(
            title="Paso 1 · Selecciona o registra el dataset",
            subtitle="Primero elige un dataset ya registrado o sube un ZIP ERP controlado. La intención de uso es subir una vez y decidir después cómo analizarlo.",
        )
        left, right = st.columns([1.05, 1.15], gap="large")
        selected_dataset = None

        with left:
            st.markdown("**Elegir dataset existente**")
            options = [""] + [item["dataset_id"] for item in datasets]
            selected_dataset_id = st.selectbox(
                "Dataset disponible",
                options=options,
                index=options.index(st.session_state.selected_dataset_id) if st.session_state.selected_dataset_id in options else 0,
                format_func=lambda value: "Selecciona un dataset" if not value else next(
                    (f"{item['file_name']} · {item['dataset_id']}" for item in datasets if item["dataset_id"] == value),
                    value,
                ),
            )
            if selected_dataset_id:
                st.session_state.selected_dataset_id = selected_dataset_id
                selected_dataset = _load_selected_dataset(client, selected_dataset_id)

        with right:
            st.markdown("**Subir ZIP ERP controlado**")
            st.caption("El flujo recomendado es registrar el ZIP para P2P y O2C y decidir el alcance del análisis en el paso siguiente.")
            uploaded_file = st.file_uploader("ZIP del ERP", type=["zip"])
            if st.button("Registrar dataset para P2P y O2C", use_container_width=True, type="primary", disabled=uploaded_file is None):
                try:
                    payload = client.upload_dataset(
                        file_name=uploaded_file.name,
                        file_bytes=uploaded_file.getvalue(),
                        scope="both",
                    )
                    st.success("Dataset registrado correctamente.")
                    st.session_state.selected_dataset_id = payload["dataset_id"]
                    selected_dataset = _load_selected_dataset(client, payload["dataset_id"])
                except APIClientError as exc:
                    st.error(f"No se pudo registrar el dataset: {exc}")

        selected_dataset = selected_dataset or _load_selected_dataset(client, st.session_state.selected_dataset_id)
        render_divider()
        render_section_heading(title="Dataset activo", subtitle="Este es el dataset que se usará al pasar al siguiente paso.")
        render_dataset_summary(selected_dataset)
        nav = st.columns([1, 1, 4])
        if nav[0].button("Continuar", type="primary", disabled=not bool(selected_dataset)):
            st.session_state.analysis_step = STEP_CONFIG
            st.rerun()

    elif step == STEP_CONFIG:
        selected_dataset = _load_selected_dataset(client, st.session_state.selected_dataset_id)
        render_section_heading(
            title="Paso 2 · Configura el análisis",
            subtitle="Ahora decide el alcance analítico, el modo LLM y si quieres forzar el rebuild del índice KB.",
        )
        render_dataset_summary(selected_dataset)
        render_divider()

        left, right = st.columns([1.2, 1.0], gap="large")
        with left:
            scope = st.radio(
                "Scope del análisis",
                SCOPE_OPTIONS,
                index=SCOPE_OPTIONS.index(st.session_state.selected_scope),
                format_func=lambda item: SCOPE_LABELS[item],
            )
            st.session_state.selected_scope = scope
            if scope == "both":
                st.info("`both` crea dos runs independientes: uno P2P y otro O2C.")
        with right:
            llm_mode = st.selectbox("LLM mode", LLM_OPTIONS, index=LLM_OPTIONS.index(st.session_state.get("llm_mode", LLM_OPTIONS[0])))
            kb_index_enabled = st.checkbox(
                "Forzar rebuild del índice KB",
                value=bool(st.session_state.get("kb_index_enabled", False)),
                help="Actívalo solo si necesitas reconstruir el índice. Si no, se reutiliza el existente.",
            )
            st.session_state.kb_index_enabled = kb_index_enabled
            st.session_state.llm_mode = llm_mode

        st.markdown(
            """
            <div class="rf20-callout tight">
                <div class="rf20-section-title">Interpretación de la configuración</div>
                <div class="rf20-section-copy">
                    El dataset se mantiene igual; aquí decides si el análisis se centra en P2P, O2C o ambos.
                    La opción <strong>P2P + O2C</strong> no fusiona familias: orquesta dos runs separados.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        nav = st.columns([1, 1, 4])
        if nav[0].button("Volver"):
            st.session_state.analysis_step = STEP_DATASET
            st.rerun()
        if nav[1].button("Continuar", type="primary", disabled=not bool(selected_dataset)):
            st.session_state.analysis_step = STEP_CONFIRM
            st.rerun()

    else:
        selected_dataset = _load_selected_dataset(client, st.session_state.selected_dataset_id)
        scope = st.session_state.selected_scope
        llm_mode = st.session_state.get("llm_mode", LLM_OPTIONS[0])
        kb_index_enabled = bool(st.session_state.get("kb_index_enabled", False))

        render_section_heading(
            title="Paso 3 · Confirma y lanza",
            subtitle="Revisa la configuración final antes de enviar la ejecución cloud.",
        )
        render_dataset_summary(selected_dataset)
        render_divider()
        st.markdown(
            f"""
            <div class="rf20-callout">
                <div class="rf20-section-title">Resumen del análisis</div>
                <div class="rf20-summary-strip">
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Dataset</div><div class="rf20-summary-value">{selected_dataset.get("dataset_id") if selected_dataset else "-"}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Scope</div><div class="rf20-summary-value">{format_scope(scope)}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">LLM mode</div><div class="rf20-summary-value">{llm_mode}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">KB rebuild</div><div class="rf20-summary-value">{format_bool(kb_index_enabled)}</div></div>
                </div>
                <div class="rf20-meta-line" style="margin-top:0.7rem;">
                    {"Se crearán dos runs separados, uno P2P y otro O2C." if scope == "both" else "Se creará un único run con el scope seleccionado."}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        nav = st.columns([1, 1, 4])
        if nav[0].button("Volver"):
            st.session_state.analysis_step = STEP_CONFIG
            st.rerun()
        if nav[1].button("Lanzar análisis", type="primary", disabled=not bool(selected_dataset)):
            try:
                payload = client.create_run(
                    dataset_id=selected_dataset["dataset_id"],
                    scope=scope,
                    pipeline_mode="graph",
                    llm_mode=llm_mode,
                    kb_index_enabled=kb_index_enabled,
                )
                remember_last_run_response(payload)
                st.success("La ejecución se ha lanzado correctamente.")
                if payload.get("composite_run"):
                    st.write(f"P2P: `{payload['run_ids'].get('p2p', '-')}`")
                    st.write(f"O2C: `{payload['run_ids'].get('o2c', '-')}`")
                else:
                    st.write(f"Run ID: `{payload.get('run_id', '-')}`")
                st.page_link("pages/2_Ejecuciones.py", label="Ir a Ejecuciones", icon=":material/monitoring:")
            except APIClientError as exc:
                st.error(f"No se pudo lanzar el análisis: {exc}")


if __name__ == "__main__":
    main()
