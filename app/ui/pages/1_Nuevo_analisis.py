from __future__ import annotations

import time

import streamlit as st

from app.ui.components.dataset_summary import render_dataset_summary
from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.constants import LLM_OPTIONS, SCOPE_LABELS, SCOPE_OPTIONS
from app.ui.utils.formatters import format_bool, format_bytes, format_scope
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


def _poll_upload_job(client: APIClient, job_id: str) -> dict | None:
    with st.status("Procesando dataset ERP...", expanded=True) as status:
        started = time.time()
        last_message = ""
        while time.time() - started < 180:
            payload = client.get_upload_dataset_job(job_id)
            message = f"{payload.get('stage', '').capitalize()}: {payload.get('message', '')}"
            if message != last_message:
                status.write(message)
                last_message = message
            if payload.get("status") == "SUCCEEDED":
                status.update(label="Dataset listo", state="complete", expanded=False)
                return payload.get("result")
            if payload.get("status") == "FAILED":
                status.update(label="Fallo al registrar el dataset", state="error", expanded=True)
                st.error(payload.get("error") or "No se pudo registrar el dataset.")
                return None
            time.sleep(1.0)
        status.update(label="Timeout esperando al backend", state="error", expanded=True)
        st.error("El dataset sigue procesándose demasiado tiempo. Reintenta o revisa el backend.")
        return None


def main() -> None:
    configure_page(page_title="Nuevo análisis")
    init_session_state()
    render_page_header(
        title="Nuevo análisis antifraude ERP",
        subtitle="Registra el ERP, define el alcance del análisis y lanza el run cloud con un flujo guiado.",
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
            title="Paso 1 · Dataset ERP",
            subtitle="Elige un dataset existente o sube un ZIP ERP controlado. La aplicación lo registrará para que luego puedas decidir si analizar P2P, O2C o ambos.",
        )
        left, right = st.columns([1.0, 1.2], gap="large")
        selected_dataset = None

        with left:
            st.markdown("**Seleccionar dataset existente**")
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
            st.caption("Formato esperado: ZIP válido del ERP fraud dataset con estructura compatible. El registro puede tardar porque valida y persiste el contenido.")
            uploaded_file = st.file_uploader("ZIP del ERP", type=["zip"])
            if uploaded_file is not None:
                st.markdown(
                    f"""
                    <div class="rf20-callout tight">
                        <div class="rf20-section-title">Fichero preparado para registrar</div>
                        <div class="rf20-summary-strip">
                            <div class="rf20-summary-item"><div class="rf20-summary-label">Nombre</div><div class="rf20-summary-value">{uploaded_file.name}</div></div>
                            <div class="rf20-summary-item"><div class="rf20-summary-label">Tipo</div><div class="rf20-summary-value">{uploaded_file.type or "application/zip"}</div></div>
                            <div class="rf20-summary-item"><div class="rf20-summary-label">Tamaño</div><div class="rf20-summary-value">{format_bytes(uploaded_file.size)}</div></div>
                            <div class="rf20-summary-item"><div class="rf20-summary-label">Registro</div><div class="rf20-summary-value">P2P + O2C</div></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if st.button("Subir y registrar dataset", use_container_width=True, type="primary", disabled=uploaded_file is None):
                if uploaded_file is None:
                    st.warning("Selecciona un ZIP válido antes de continuar.")
                elif not uploaded_file.name.lower().endswith(".zip"):
                    st.error("El fichero debe ser un ZIP.")
                else:
                    try:
                        job = client.start_upload_dataset_job(
                            file_name=uploaded_file.name,
                            file_bytes=uploaded_file.getvalue(),
                            scope="both",
                        )
                        result = _poll_upload_job(client, job["job_id"])
                        if result:
                            st.session_state.selected_dataset_id = result["dataset_id"]
                            selected_dataset = _load_selected_dataset(client, result["dataset_id"])
                            st.success("Dataset listo para análisis.")
                    except APIClientError as exc:
                        st.error(f"No se pudo iniciar el registro del dataset: {exc}")

        selected_dataset = selected_dataset or _load_selected_dataset(client, st.session_state.selected_dataset_id)
        render_divider()
        render_section_heading(title="Dataset activo", subtitle="Este dataset se usará en el resto del flujo.")
        render_dataset_summary(selected_dataset)
        nav = st.columns([1, 1, 4])
        if nav[0].button("Continuar", type="primary", disabled=not bool(selected_dataset)):
            st.session_state.analysis_step = STEP_CONFIG
            st.rerun()

    elif step == STEP_CONFIG:
        selected_dataset = _load_selected_dataset(client, st.session_state.selected_dataset_id)
        render_section_heading(
            title="Paso 2 · Configuración del análisis",
            subtitle="Define el alcance del análisis, el modo LLM y si quieres forzar reconstrucción del índice KB.",
        )
        render_dataset_summary(selected_dataset)
        render_divider()

        left, right = st.columns([1.15, 1.0], gap="large")
        with left:
            scope = st.radio(
                "Alcance del análisis",
                SCOPE_OPTIONS,
                index=SCOPE_OPTIONS.index(st.session_state.selected_scope),
                format_func=lambda item: SCOPE_LABELS[item],
            )
            st.session_state.selected_scope = scope
            if scope == "both":
                st.info("Esta opción lanza dos runs separados: uno para P2P y otro para O2C.")
        with right:
            llm_mode = st.selectbox("LLM mode", LLM_OPTIONS, index=LLM_OPTIONS.index(st.session_state.get("llm_mode", LLM_OPTIONS[0])))
            kb_index_enabled = st.checkbox(
                "Forzar rebuild del índice KB",
                value=bool(st.session_state.get("kb_index_enabled", False)),
                help="Úsalo solo si necesitas regenerar explícitamente el índice de conocimiento.",
            )
            st.session_state.kb_index_enabled = kb_index_enabled
            st.session_state.llm_mode = llm_mode

        st.markdown(
            """
            <div class="rf20-callout tight">
                <div class="rf20-section-title">Qué va a hacer el sistema</div>
                <div class="rf20-section-copy">
                    Ejecutará el pipeline <strong>graph</strong> sobre el dataset activo. Si eliges <strong>P2P + O2C</strong>,
                    el sistema orquesta dos runs independientes para conservar la semántica correcta del backend.
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
            title="Paso 3 · Confirmación",
            subtitle="Revisa la configuración final y lanza el análisis cloud.",
        )
        render_dataset_summary(selected_dataset)
        render_divider()
        st.markdown(
            f"""
            <div class="rf20-callout">
                <div class="rf20-section-title">Resumen final</div>
                <div class="rf20-summary-strip">
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Dataset</div><div class="rf20-summary-value">{selected_dataset.get("dataset_id") if selected_dataset else "-"}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">Scope</div><div class="rf20-summary-value">{format_scope(scope)}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">LLM mode</div><div class="rf20-summary-value">{llm_mode}</div></div>
                    <div class="rf20-summary-item"><div class="rf20-summary-label">KB rebuild</div><div class="rf20-summary-value">{format_bool(kb_index_enabled)}</div></div>
                </div>
                <div class="rf20-meta-line" style="margin-top:0.7rem;">
                    {"Se crearán dos runs: uno P2P y otro O2C." if scope == "both" else "Se lanzará un único run con el alcance seleccionado."}
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
