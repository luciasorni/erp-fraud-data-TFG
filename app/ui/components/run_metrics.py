from __future__ import annotations

import streamlit as st
from typing import Dict


def render_run_metrics(metrics: Dict[str, int]) -> None:
    cols = st.columns(4)
    cols[0].metric("Total ejecuciones", metrics.get("total", 0))
    cols[1].metric("Completadas", metrics.get("completed", 0))
    cols[2].metric("En curso", metrics.get("running", 0))
    cols[3].metric("Fallidas", metrics.get("failed", 0))


def render_result_kpis(kpis: Dict[str, int], *, score_value: str) -> None:
    cols = st.columns(4)
    cols[0].metric("Hypotheses", kpis.get("hypotheses", 0))
    cols[1].metric("Selected tests", kpis.get("selected_tests", 0))
    cols[2].metric("Findings", kpis.get("findings", 0))
    cols[3].metric("Score agregado", score_value)
