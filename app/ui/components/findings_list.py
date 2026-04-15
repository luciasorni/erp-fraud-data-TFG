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
    for row in rows:
        st.markdown('<div class="rf20-panel">', unsafe_allow_html=True)
        top_left, top_right = st.columns([4.2, 1.0])
        with top_left:
            st.markdown(
                f'<div class="rf20-heading">{row.get("title") or row.get("finding_id")}</div>'
                f'<div class="rf20-subline">{row.get("finding_id") or "-"}</div>',
                unsafe_allow_html=True,
            )
        with top_right:
            render_status_badge(row.get("status"))
        if row.get("summary"):
            st.markdown(f'<div class="rf20-body">{row.get("summary")}</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="rf20-meta-grid">
                <div class="rf20-meta-item">
                    <div class="rf20-meta-label">Test asociado</div>
                    <div class="rf20-meta-value">{row.get("test_id") or "-"}</div>
                </div>
                <div class="rf20-meta-item">
                    <div class="rf20-meta-label">Fraud type</div>
                    <div class="rf20-meta-value">{row.get("fraud_type") or "-"}</div>
                </div>
                <div class="rf20-meta-item">
                    <div class="rf20-meta-label">Registros afectados</div>
                    <div class="rf20-meta-value">{row.get("finding_count") or 0}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Ver detalle", key=f"finding-detail-{row.get('finding_id')}"):
            if on_select:
                on_select(row)
        st.markdown("</div>", unsafe_allow_html=True)
