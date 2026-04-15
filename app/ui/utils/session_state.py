from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional

from .constants import DEFAULT_RUN_FILTERS


def init_session_state() -> None:
    defaults = {
        "selected_dataset_id": None,
        "selected_scope": "p2p",
        "analysis_step": 1,
        "llm_mode": "real",
        "kb_index_enabled": False,
        "selected_run_id": None,
        "selected_run_ids": {},
        "selected_finding_id": None,
        "selected_finding": None,
        "selected_finding_row_key": None,
        "selected_graph_payload": None,
        "selected_run_detail": None,
        "last_run_response": None,
        "runs_filters": dict(DEFAULT_RUN_FILTERS),
        "drilldown_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def remember_run_selection(*, run_id: str, run_detail: Optional[Dict[str, Any]] = None) -> None:
    st.session_state.selected_run_id = run_id
    st.session_state.selected_run_detail = run_detail


def remember_finding_selection(*, finding_id: str, finding: Optional[Dict[str, Any]] = None) -> None:
    st.session_state.selected_finding_id = finding_id
    st.session_state.selected_finding = finding
    st.session_state.selected_finding_row_key = None


def remember_last_run_response(payload: dict) -> None:
    st.session_state.last_run_response = payload
    run_ids = payload.get("run_ids") or {}
    st.session_state.selected_run_ids = run_ids
    if payload.get("run_id"):
        st.session_state.selected_run_id = payload["run_id"]
