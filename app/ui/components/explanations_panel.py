from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from app.ui.components.recommendations_panel import render_presentable_content


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
        st.markdown("### Explicación del fraude detectado")

    for item in narrative_items:
        attrs = item.get("attributes", {}) or {}
        process_step = attrs.get("process_step") or item.get("process_step") or "-"
        fraud_type = item.get("fraud_type") or attrs.get("fraud_type") or "-"
        finding_count = item.get("finding_count") or attrs.get("finding_count") or "-"

        with st.container(border=True):
            st.markdown(f"#### {item.get('title') or item.get('id') or 'Explicación'}")
            if item.get("subtitle"):
                st.caption(str(item.get("subtitle")))

            meta_cols = st.columns(3, gap="small")
            with meta_cols[0]:
                st.caption("Tipología")
                st.markdown(f"**{fraud_type}**")
            with meta_cols[1]:
                st.caption("Paso afectado")
                st.markdown(f"**{process_step}**")
            with meta_cols[2]:
                st.caption("Hallazgos")
                st.markdown(f"**{finding_count}**")

            render_presentable_content(item.get("summary") or "Sin resumen explicativo.")

    if technical_items:
        st.markdown("### Incidencias técnicas de ejecución")

        for item in technical_items:
            with st.container(border=True):
                st.markdown(f"#### {item.get('title') or item.get('id') or 'Test con incidencia'}")
                st.caption(f"{item.get('subtitle') or ''} · {item.get('status') or 'ERROR'}")
                render_presentable_content(
                    item.get("summary") or "El test no pudo generar una explicación utilizable."
                )