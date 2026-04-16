from __future__ import annotations

import streamlit as st
from typing import Any, Dict, List

from app.ui.utils.formatters import normalize_structured_content, presentable_label, summarize_structured_content


def render_presentable_content(value: Any) -> None:
    normalized = normalize_structured_content(value)
    if normalized is None or normalized == "":
        st.caption("Sin detalle adicional.")
        return
    if isinstance(normalized, dict):
        for key, item in normalized.items():
            label = presentable_label(key)
            if isinstance(item, dict):
                st.markdown(f"**{label}**")
                render_presentable_content(item)
            elif isinstance(item, list):
                st.markdown(f"**{label}**")
                if all(not isinstance(entry, (dict, list)) for entry in item):
                    for entry in item:
                        text = summarize_structured_content(entry)
                        if text != "-":
                            st.markdown(f"- {text}")
                else:
                    for entry in item:
                        render_presentable_content(entry)
            else:
                text = summarize_structured_content(item)
                if text != "-":
                    st.markdown(f"**{label}:** {text}")
        return
    if isinstance(normalized, list):
        if all(not isinstance(entry, (dict, list)) for entry in normalized):
            for entry in normalized:
                text = summarize_structured_content(entry)
                if text != "-":
                    st.markdown(f"- {text}")
        else:
            for entry in normalized:
                render_presentable_content(entry)
        return
    st.markdown(summarize_structured_content(normalized))


def render_recommendations_panel(
    recommendations: List[Dict[str, Any]],
    *,
    title: str = "Recomendaciones y siguientes pasos",
    empty_message: str = "No hay recomendaciones adicionales disponibles.",
) -> None:
    if not recommendations:
        st.info(empty_message)
        return
    st.markdown(f"#### {title}")
    for item in recommendations:
        st.markdown('<div class="rf20-recommendation">', unsafe_allow_html=True)
        st.markdown(f"**{item.get('title') or title}**")
        if item.get("subtitle"):
            st.caption(str(item.get("subtitle")))
        render_presentable_content(item.get("summary") or "Sin recomendación detallada.")
        st.markdown("</div>", unsafe_allow_html=True)
