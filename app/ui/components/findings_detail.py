from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from app.ui.components.recommendations_panel import render_presentable_content


def render_finding_detail(finding: Optional[Dict[str, Any]]) -> None:
    if not finding:
        st.info("Selecciona un hallazgo para ver su detalle.")
        return

    with st.container(border=True):
        st.caption("TEST Y HALLAZGOS ASOCIADOS")
        st.markdown(f"### {finding.get('title') or finding.get('test_id') or 'Hallazgo'}")
        st.caption(finding.get("test_id") or "-")

        cols = st.columns(4, gap="small")
        summary_items = [
            ("Test asociado", finding.get("test_id") or "-"),
            ("Fraud type", finding.get("fraud_type") or "-"),
            ("Hallazgos detectados", finding.get("finding_count") or 0),
            ("Paso afectado", finding.get("process_step") or "-"),
        ]
        for col, (label, value) in zip(cols, summary_items):
            with col:
                st.caption(label)
                st.markdown(f"**{value}**")

    if finding.get("summary"):
        st.write("")
        render_presentable_content(finding.get("summary"))

    if finding.get("drilldown_error"):
        st.warning(str(finding.get("drilldown_error")))