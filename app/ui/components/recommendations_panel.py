from __future__ import annotations

import streamlit as st
from typing import Any, Dict, List


def render_recommendations_panel(recommendations: List[Dict[str, Any]]) -> None:
    if not recommendations:
        st.info("No hay recomendaciones adicionales disponibles.")
        return
    st.markdown("#### Recomendaciones y siguientes pasos")
    for item in recommendations:
        st.markdown(
            f"""
            <div class="rf20-recommendation">
                <div class="rf20-list-title">{item.get('title') or 'Recomendación'}</div>
                <div class="rf20-list-subtitle">{item.get("subtitle") or ""}</div>
                <div class="rf20-meta-line">{item.get("summary") or "Sin recomendación detallada."}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
