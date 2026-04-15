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
    for item in runs:
        st.markdown('<div class="rf20-panel soft">', unsafe_allow_html=True)
        top_left, top_right = st.columns([4.3, 1.0])
        with top_left:
            st.markdown(f'<div class="rf20-kicker">Run</div><div class="rf20-heading">{item.get("run_id", "-")}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="rf20-subline">{item.get("dataset_id") or "-"} · {format_scope(item.get("scope"))} · {format_datetime(item.get("created_at_utc"))}</div>',
                unsafe_allow_html=True,
            )
        with top_right:
            render_status_badge(item.get("status"))
        meta = st.columns(4)
        meta[0].markdown(
            f'<div class="rf20-meta-item"><div class="rf20-meta-label">KB rebuild</div><div class="rf20-meta-value">{format_bool(item.get("kb_index_enabled"))}</div></div>',
            unsafe_allow_html=True,
        )
        meta[1].markdown(
            f'<div class="rf20-meta-item"><div class="rf20-meta-label">Última actualización</div><div class="rf20-meta-value">{format_datetime(item.get("updated_at_utc"))}</div></div>',
            unsafe_allow_html=True,
        )
        meta[2].markdown(
            f'<div class="rf20-meta-item"><div class="rf20-meta-label">Graph status</div><div class="rf20-meta-value">{item.get("graph_status") or "-"}</div></div>',
            unsafe_allow_html=True,
        )
        meta[3].markdown(
            f'<div class="rf20-meta-item"><div class="rf20-meta-label">KB index</div><div class="rf20-meta-value">{item.get("kb_index_status") or "-"}</div></div>',
            unsafe_allow_html=True,
        )
        action_col = st.columns([1, 6])[0]
        if action_col.button("Abrir", key=f"open-run-{item.get('run_id')}"):
            if on_open:
                on_open(str(item.get("run_id")))
        st.markdown("</div>", unsafe_allow_html=True)
