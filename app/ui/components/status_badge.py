from __future__ import annotations

import streamlit as st
from typing import Optional

from app.ui.utils.constants import STATUS_COLORS
from app.ui.utils.formatters import format_status


def render_status_badge(status: Optional[str], *, label: Optional[str] = None) -> None:
    value = (status or "UNKNOWN").upper()
    text = label or format_status(value)
    color = STATUS_COLORS.get(value, STATUS_COLORS["UNKNOWN"])
    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:0.2rem 0.62rem;
            border-radius:999px;
            background:{color}15;
            color:{color};
            border:1px solid {color}4D;
            font-weight:700;
            font-size:0.74rem;
            line-height:1.2;
            letter-spacing:0.01em;
        ">{text}</span>
        """,
        unsafe_allow_html=True,
    )
