from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional

from app.ui.utils.formatters import format_bytes, format_datetime


def render_dataset_summary(dataset: Optional[Dict[str, Any]]) -> None:
    if not dataset:
        st.info("Selecciona o sube un dataset para ver su resumen.")
        return
    scopes = ", ".join(str(item).upper() for item in dataset.get("scopes", [])) or "-"
    st.markdown(
        f"""
        <div class="rf20-callout tight">
            <div class="rf20-list-title">{dataset.get('file_name', '-')}</div>
            <div class="rf20-list-subtitle">{dataset.get("dataset_id", "-")}</div>
            <div class="rf20-summary-strip">
                <div class="rf20-summary-item"><div class="rf20-summary-label">Validación</div><div class="rf20-summary-value">{dataset.get("validation_status", "-")}</div></div>
                <div class="rf20-summary-item"><div class="rf20-summary-label">Fecha de alta</div><div class="rf20-summary-value">{format_datetime(dataset.get("uploaded_at_utc"))}</div></div>
                <div class="rf20-summary-item"><div class="rf20-summary-label">Tamaño</div><div class="rf20-summary-value">{format_bytes(dataset.get("size_bytes"))}</div></div>
                <div class="rf20-summary-item"><div class="rf20-summary-label">Scopes</div><div class="rf20-summary-value">{scopes}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
