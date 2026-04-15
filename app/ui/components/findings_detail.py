from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional


def render_finding_detail(finding: Optional[Dict[str, Any]]) -> None:
    if not finding:
        st.info("Selecciona un hallazgo para ver su detalle.")
        return
    st.markdown(
        f"""
        <div class="rf20-pagehead" style="padding-bottom:0.9rem; margin-bottom:1rem;">
            <div class="rf20-eyebrow">Test y hallazgos asociados</div>
            <div class="rf20-title" style="font-size:1.35rem; margin-bottom:0.12rem;">{finding.get('title') or finding.get('test_id') or 'Hallazgo'}</div>
            <div class="rf20-subtitle">{finding.get("test_id") or "-"}</div>
            <div class="rf20-lead" style="font-size:0.98rem; margin-top:0.45rem;">{finding.get("summary") or "Sin resumen adicional."}</div>
            <div class="rf20-summary-strip">
                <div class="rf20-summary-item"><div class="rf20-summary-label">Test asociado</div><div class="rf20-summary-value">{finding.get("test_id") or "-"}</div></div>
                <div class="rf20-summary-item"><div class="rf20-summary-label">Fraud type</div><div class="rf20-summary-value">{finding.get("fraud_type") or "-"}</div></div>
                <div class="rf20-summary-item"><div class="rf20-summary-label">Hallazgos detectados</div><div class="rf20-summary-value">{finding.get("finding_count") or 0}</div></div>
                <div class="rf20-summary-item"><div class="rf20-summary-label">Paso afectado</div><div class="rf20-summary-value">{finding.get("process_step") or "-"}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
