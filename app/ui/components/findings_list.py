from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from app.ui.components.status_badge import render_status_badge


def render_findings_list(
    rows: List[Dict[str, Any]],
    *,
    on_select: Optional[Callable[[dict], None]] = None,
) -> None:
    if not rows:
        st.info("No hay hallazgos para mostrar en este run.")
        return
    st.markdown('<div class="rf20-list">', unsafe_allow_html=True)
    for row in rows:
        st.markdown('<div class="rf20-list-item">', unsafe_allow_html=True)
        top_left, top_right = st.columns([5.0, 1.0])
        with top_left:
            st.markdown(
                f'<div class="rf20-list-title">{row.get("title") or row.get("finding_id")}</div>'
                f'<div class="rf20-list-subtitle">{row.get("finding_id") or "-"}</div>',
                unsafe_allow_html=True,
            )
        with top_right:
            render_status_badge(row.get("status"))
        if row.get("summary"):
            st.markdown(f'<div class="rf20-meta-line">{row.get("summary")}</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="rf20-meta-line">
                Test asociado: <span class="rf20-meta-inline">{row.get("test_id") or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Fraud type: <span class="rf20-meta-inline">{row.get("fraud_type") or "-"}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Registros afectados: <span class="rf20-meta-inline">{row.get("finding_count") or 0}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Ver detalle", key=f"finding-detail-{row.get('finding_id')}"):
            if on_select:
                on_select(row)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
