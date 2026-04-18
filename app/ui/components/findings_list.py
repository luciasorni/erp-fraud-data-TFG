from __future__ import annotations

from typing import Callable, Dict, List, Optional

import streamlit as st

from app.ui.components.recommendations_panel import render_presentable_content
from app.ui.components.status_badge import render_status_badge


def render_findings_list(
    rows: List[Dict],
    *,
    on_select: Optional[Callable[[dict], None]] = None,
) -> None:
    if not rows:
        st.info("No hay hallazgos para mostrar en este run.")
        return

    for row in rows:
        with st.container(border=True):
            head_left, head_right = st.columns([5.0, 1.0], gap="small")

            with head_left:
                st.markdown(f"### {row.get('title') or row.get('finding_id')}")
                if row.get("finding_id"):
                    st.caption(str(row.get("finding_id")))

            with head_right:
                render_status_badge(row.get("status"))

            if row.get("summary"):
                render_presentable_content(row.get("summary"))

            meta_cols = st.columns(3, gap="small")
            with meta_cols[0]:
                st.caption("Test asociado")
                st.markdown(f"**{row.get('test_id') or '-'}**")
            with meta_cols[1]:
                st.caption("Fraud type")
                st.markdown(f"**{row.get('fraud_type') or 'No disponible en este run'}**")
            with meta_cols[2]:
                st.caption("Registros afectados")
                st.markdown(f"**{row.get('finding_count_text') or row.get('finding_count') or 0}**")

            if row.get("process_step"):
                st.caption(f"Paso afectado: {row.get('process_step')}")

            if row.get("error_summary"):
                st.caption(str(row.get("error_summary")))

            if st.button("Ver detalle", key=f"finding-detail-{row.get('finding_id')}"):
                if on_select:
                    on_select(row)
