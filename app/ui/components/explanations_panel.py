from __future__ import annotations

import streamlit as st
from typing import Any, Dict, List


def render_explanations_panel(explanations: List[Dict[str, Any]]) -> None:
    if not explanations:
        st.info("No hay explicación narrativa disponible para este run.")
        return
    st.markdown("#### Explicación del fraude detectado")
    for item in explanations:
        st.markdown(
            f"""
            <div class="rf20-panel narrative">
                <div class="rf20-heading">{item.get('title') or item.get('id') or 'Explicación'}</div>
                <div class="rf20-subline">{item.get("subtitle") or ""}</div>
                <div class="rf20-body">{item.get("summary") or "Sin resumen explicativo."}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
