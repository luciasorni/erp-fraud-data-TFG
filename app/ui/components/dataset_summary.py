from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional

from app.ui.utils.formatters import format_bytes, format_datetime


def render_dataset_summary(dataset: Optional[Dict[str, Any]]) -> None:
    if not dataset:
        st.info("Selecciona o sube un dataset para ver su resumen.")
        return
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**{dataset.get('file_name', '-') }**")
            st.caption(dataset.get("dataset_id", "-"))
        with col2:
            st.markdown(f"**Validación:** {dataset.get('validation_status', '-')}")
        col3, col4, col5 = st.columns(3)
        col3.metric("Fecha de alta", format_datetime(dataset.get("uploaded_at_utc")))
        col4.metric("Tamaño", format_bytes(dataset.get("size_bytes")))
        scopes = ", ".join(str(item).upper() for item in dataset.get("scopes", [])) or "-"
        col5.metric("Scopes", scopes)
