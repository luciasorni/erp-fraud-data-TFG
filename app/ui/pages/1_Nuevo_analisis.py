from __future__ import annotations

import streamlit as st

from app.ui.components.dataset_summary import render_dataset_summary
from app.ui.components.header import configure_page, render_page_header
from app.ui.services.api_client import APIClient, APIClientError
from app.ui.utils.constants import LLM_OPTIONS, PIPELINE_OPTIONS, SCOPE_LABELS, SCOPE_OPTIONS
from app.ui.utils.formatters import format_bool, format_scope
from app.ui.utils.session_state import init_session_state, remember_last_run_response


def main() -> None:
    configure_page(page_title="Nuevo análisis")
    init_session_state()
    render_page_header(
        title="Nuevo análisis antifraude ERP",
        subtitle="Carga o selecciona un dataset ERP y lanza un análisis sobre P2P, O2C o ambos.",
    )

    client = APIClient()
    datasets = []
    selected_dataset = None
    try:
        datasets = client.list_datasets()
    except APIClientError as exc:
        st.error(f"No se pudieron cargar los datasets: {exc}")

    st.markdown("### Dataset")
    dataset_col, upload_col = st.columns([1.15, 1.0], gap="large")

    with dataset_col:
        options = [""] + [item["dataset_id"] for item in datasets]
        selected_dataset_id = st.selectbox(
            "Dataset existente",
            options=options,
            index=options.index(st.session_state.selected_dataset_id) if st.session_state.selected_dataset_id in options else 0,
            format_func=lambda value: "Selecciona un dataset" if not value else next(
                (f"{item['file_name']} · {item['dataset_id']}" for item in datasets if item["dataset_id"] == value),
                value,
            ),
        )
        if selected_dataset_id:
            st.session_state.selected_dataset_id = selected_dataset_id
            try:
                selected_dataset = client.get_dataset(selected_dataset_id)
            except APIClientError as exc:
                st.error(f"No se pudo cargar el detalle del dataset: {exc}")

    with upload_col:
        st.markdown("**Subir ZIP controlado**")
        upload_scope = st.selectbox("Scope del dataset subido", SCOPE_OPTIONS, format_func=lambda item: SCOPE_LABELS[item], key="upload_scope")
        uploaded_file = st.file_uploader("ZIP del dataset ERP", type=["zip"])
        if st.button("Registrar dataset", type="secondary", use_container_width=True, disabled=uploaded_file is None):
            if uploaded_file is None:
                st.warning("Selecciona un fichero ZIP antes de subirlo.")
            else:
                try:
                    payload = client.upload_dataset(
                        file_name=uploaded_file.name,
                        file_bytes=uploaded_file.getvalue(),
                        scope=upload_scope,
                    )
                    st.success("Dataset registrado correctamente.")
                    st.session_state.selected_dataset_id = payload["dataset_id"]
                    selected_dataset = client.get_dataset(payload["dataset_id"])
                except APIClientError as exc:
                    st.error(f"No se pudo registrar el dataset: {exc}")

    render_dataset_summary(selected_dataset)

    st.markdown("### Configuración del análisis")
    cfg1, cfg2, cfg3 = st.columns(3)
    scope = cfg1.selectbox("Scope", SCOPE_OPTIONS, index=SCOPE_OPTIONS.index(st.session_state.selected_scope), format_func=lambda item: SCOPE_LABELS[item])
    pipeline_mode = cfg2.selectbox("Pipeline mode", PIPELINE_OPTIONS, index=0, disabled=True)
    llm_mode = cfg3.selectbox("LLM mode", LLM_OPTIONS, index=0)
    st.session_state.selected_scope = scope
    kb_index_enabled = st.checkbox(
        "Reconstruir índice KB",
        value=False,
        help="Solo actívalo cuando necesites forzar el rebuild del índice de conocimiento. Si no, se reutiliza la base existente.",
    )
    if scope == "both":
        st.info("`both` lanza dos runs separados: uno para P2P y otro para O2C.")

    st.markdown("### Resumen antes de lanzar")
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Dataset", selected_dataset.get("dataset_id") if selected_dataset else "-")
        col2.metric("Scope", format_scope(scope))
        col3.metric("LLM mode", llm_mode)
        col4.metric("KB rebuild", format_bool(kb_index_enabled))

    st.markdown("### Acción")
    launch_disabled = not bool(selected_dataset and selected_dataset.get("dataset_id"))
    if st.button("Lanzar análisis", type="primary", use_container_width=True, disabled=launch_disabled):
        try:
            payload = client.create_run(
                dataset_id=selected_dataset["dataset_id"],
                scope=scope,
                pipeline_mode=pipeline_mode,
                llm_mode=llm_mode,
                kb_index_enabled=kb_index_enabled,
            )
            remember_last_run_response(payload)
            st.success("La ejecución se ha lanzado correctamente.")
            if payload.get("composite_run"):
                st.markdown("**Runs creados**")
                st.write(f"P2P: `{payload['run_ids'].get('p2p', '-')}`")
                st.write(f"O2C: `{payload['run_ids'].get('o2c', '-')}`")
            else:
                st.write(f"Run ID: `{payload.get('run_id', '-')}`")
            st.page_link("pages/2_Ejecuciones.py", label="Ir a Ejecuciones", icon=":material/monitoring:")
        except APIClientError as exc:
            st.error(f"No se pudo lanzar el análisis: {exc}")


if __name__ == "__main__":
    main()
