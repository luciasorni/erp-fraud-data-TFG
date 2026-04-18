from __future__ import annotations

from typing import Dict

import streamlit as st


def _render_metric_card(label: str, value: str | int, *, help_text: str | None = None) -> None:
    with st.container(border=True):
        st.caption(label.upper())
        st.markdown(f"## {value}")
        if help_text:
            st.caption(help_text)


def render_run_metrics(metrics: Dict[str, int]) -> None:
    cols = st.columns(4, gap="small")

    items = [
        ("Total ejecuciones", metrics.get("total", 0), "Runs visibles en el historial."),
        ("Completadas", metrics.get("completed", 0), "Runs finalizadas correctamente."),
        ("En curso", metrics.get("running", 0), "Runs todavía activas o pendientes."),
        ("Fallidas", metrics.get("failed", 0), "Runs terminadas con error."),
    ]

    for col, (label, value, help_text) in zip(cols, items):
        with col:
            _render_metric_card(label, value, help_text=help_text)


def render_result_kpis(kpis: Dict[str, int], *, score_value: str, help_texts: Dict[str, str] | None = None) -> None:
    cols = st.columns(4, gap="small")
    help_texts = help_texts or {}

    items = [
        ("Hypotheses", kpis.get("hypotheses", 0), help_texts.get("hypotheses") or "Hipótesis activas en el análisis."),
        ("Selected tests", kpis.get("selected_tests", 0), help_texts.get("selected_tests") or "Tests priorizados por el planner."),
        ("Findings", kpis.get("findings", 0), help_texts.get("findings") or "Hallazgos disponibles en el run."),
        ("Score agregado", score_value, help_texts.get("score") or "Señal consolidada del scoring."),
    ]

    for col, (label, value, help_text) in zip(cols, items):
        with col:
            _render_metric_card(label, value, help_text=help_text)
