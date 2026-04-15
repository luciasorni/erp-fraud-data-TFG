from __future__ import annotations

import streamlit as st
from typing import Any, Dict, List


def render_explanations_panel(explanations: List[Dict[str, Any]]) -> None:
    if not explanations:
        st.info("No hay explicación narrativa disponible para este run.")
        return
    narrative_items = []
    technical_items = []
    for item in explanations:
        attrs = item.get("attributes", {}) or {}
        if attrs.get("technical_error"):
            technical_items.append(item)
        else:
            narrative_items.append(item)

    if narrative_items:
        st.markdown("#### Explicación del fraude detectado")
    for item in narrative_items:
        attrs = item.get("attributes", {}) or {}
        st.markdown(
            f"""
            <div class="rf20-narrative">
                <div class="rf20-list-title">{item.get('title') or item.get('id') or 'Explicación'}</div>
                <div class="rf20-list-subtitle">{item.get("subtitle") or ""}</div>
                <div class="rf20-meta-line">{item.get("summary") or "Sin resumen explicativo."}</div>
                <div class="rf20-mini-note">Paso afectado: {attrs.get("process_step") or "-"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if technical_items:
        st.markdown("#### Incidencias técnicas de ejecución")
        for item in technical_items:
            st.markdown(
                f"""
                <div class="rf20-callout tight" style="border-color:#E7C7C2; background:#FFF8F6; margin-bottom:0.75rem;">
                    <div class="rf20-list-title">{item.get('title') or item.get('id') or 'Test con incidencia'}</div>
                    <div class="rf20-list-subtitle">{item.get("subtitle") or ""} · {item.get("status") or "ERROR"}</div>
                    <div class="rf20-meta-line">{item.get("summary") or "El test no pudo generar una explicación utilizable."}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
