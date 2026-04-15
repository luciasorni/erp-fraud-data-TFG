from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional


def render_finding_detail(finding: Optional[Dict[str, Any]]) -> None:
    if not finding:
        st.info("Selecciona un hallazgo para ver su detalle.")
        return
    st.markdown(
        f"""
        <div class="rf20-section">
            <div class="rf20-kicker">Hallazgo</div>
            <div class="rf20-title" style="font-size:1.3rem; margin-bottom:0.15rem;">{finding.get('title') or 'Hallazgo'}</div>
            <div class="rf20-subline">{finding.get("finding_id") or finding.get("test_id") or "-"}</div>
            <div class="rf20-body">{finding.get("summary") or "Sin resumen adicional."}</div>
            <div class="rf20-summary-grid">
                <div class="rf20-summary-card">
                    <div class="rf20-summary-label">Test asociado</div>
                    <div class="rf20-summary-value">{finding.get("test_id") or "-"}</div>
                </div>
                <div class="rf20-summary-card">
                    <div class="rf20-summary-label">Fraud type</div>
                    <div class="rf20-summary-value">{finding.get("fraud_type") or "-"}</div>
                </div>
                <div class="rf20-summary-card">
                    <div class="rf20-summary-label">Registros afectados</div>
                    <div class="rf20-summary-value">{finding.get("finding_count") or 0}</div>
                </div>
                <div class="rf20-summary-card">
                    <div class="rf20-summary-label">Entity key</div>
                    <div class="rf20-summary-value">{finding.get("sample_entity_key") or "-"}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    sample_keys = finding.get("sample_keys") or {}
    if sample_keys:
        st.markdown("**Claves de evidencia**")
        st.table([{"campo": key, "valor": value} for key, value in sample_keys.items()])
