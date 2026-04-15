from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from app.ui.components.status_badge import render_status_badge
from app.ui.utils.formatters import format_bool, format_datetime, format_scope


def render_run_table(
    runs: List[Dict[str, Any]],
    *,
    on_open: Optional[Callable[[str], None]] = None,
) -> None:
    if not runs:
        st.info("No hay ejecuciones para los filtros seleccionados.")
        return
    st.markdown('<div class="rf20-list">', unsafe_allow_html=True)
    for item in runs:
        st.markdown('<div class="rf20-list-item">', unsafe_allow_html=True)
        top_left, top_right = st.columns([5.2, 1.0])
        with top_left:
            st.markdown(f'<div class="rf20-list-title">{item.get("run_id", "-")}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="rf20-list-subtitle">{item.get("dataset_id") or "-"} · {format_scope(item.get("scope"))} · {format_datetime(item.get("created_at_utc"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div class="rf20-meta-line">
                    KB rebuild: <span class="rf20-meta-inline">{format_bool(item.get("kb_index_enabled"))}</span>
                    &nbsp;&nbsp;·&nbsp;&nbsp;
                    Graph status: <span class="rf20-meta-inline">{item.get("graph_status") or "-"}</span>
                    &nbsp;&nbsp;·&nbsp;&nbsp;
                    KB index: <span class="rf20-meta-inline">{item.get("kb_index_status") or "-"}</span>
                    &nbsp;&nbsp;·&nbsp;&nbsp;
                    Última actualización: <span class="rf20-meta-inline">{format_datetime(item.get("updated_at_utc"))}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with top_right:
            render_status_badge(item.get("status"))
        action_col = st.columns([1, 6])[0]
        if action_col.button("Abrir", key=f"open-run-{item.get('run_id')}"):
            if on_open:
                on_open(str(item.get("run_id")))
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
