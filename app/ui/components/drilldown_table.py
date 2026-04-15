from __future__ import annotations

import pandas as pd
import streamlit as st
from typing import Any, Dict, Optional


def render_drilldown_table(drilldown_result: Optional[Dict[str, Any]]) -> None:
    if not drilldown_result:
        st.info("Ejecuta el drilldown para ver la evidencia detallada.")
        return
    rows = drilldown_result.get("rows", []) or []
    st.markdown(f"**Filas recuperadas:** {drilldown_result.get('row_count', 0)}")
    if not rows:
        st.warning("El drilldown no devolvió filas.")
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
