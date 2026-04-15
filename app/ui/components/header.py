from __future__ import annotations

import streamlit as st

from app.ui.utils.constants import APP_SUBTITLE, APP_TITLE


def configure_page(*, page_title: str, layout: str = "wide") -> None:
    st.set_page_config(page_title=page_title, page_icon=":bar_chart:", layout=layout)


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --rf20-bg: #F3F4F1;
            --rf20-surface: #FFFFFF;
            --rf20-surface-soft: #F7F8F6;
            --rf20-surface-muted: #EEF2F0;
            --rf20-border: #D8E2DD;
            --rf20-border-strong: #C6D3CD;
            --rf20-text: #12302B;
            --rf20-text-soft: #526662;
            --rf20-text-muted: #70817C;
            --rf20-primary: #0F766E;
            --rf20-primary-soft: #E5F2EF;
            --rf20-ok: #0F766E;
            --rf20-warn: #B76E12;
            --rf20-error: #B42318;
            --rf20-neutral: #5E6F79;
            --rf20-shadow: 0 10px 28px rgba(16, 24, 40, 0.04);
        }
        .stApp {
            background: var(--rf20-bg);
        }
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2rem;
            max-width: 1180px;
        }
        h1, h2, h3, h4 {
            color: var(--rf20-text);
            letter-spacing: -0.02em;
        }
        div[data-testid="stMetric"] {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            box-shadow: var(--rf20-shadow);
        }
        div[data-testid="stMetric"] label {
            color: var(--rf20-text-soft);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-weight: 700;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.45rem;
            font-weight: 700;
            color: var(--rf20-text);
        }
        div[data-baseweb="tab-list"] {
            gap: 0.45rem;
            margin-top: 0.35rem;
            margin-bottom: 0.8rem;
        }
        button[data-baseweb="tab"] {
            background: var(--rf20-surface-muted);
            border-radius: 999px;
            padding: 0.35rem 0.95rem;
            border: 1px solid transparent;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: var(--rf20-surface);
            border-color: var(--rf20-border-strong);
        }
        div[data-testid="stExpander"] {
            border: 1px solid var(--rf20-border);
            border-radius: 16px;
            background: var(--rf20-surface-soft);
        }
        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid var(--rf20-border);
        }
        .rf20-hero {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border-strong);
            border-radius: 22px;
            padding: 1.25rem 1.35rem;
            margin-bottom: 1rem;
            box-shadow: var(--rf20-shadow);
        }
        .rf20-eyebrow {
            letter-spacing: .08em;
            font-size: 0.7rem;
            text-transform: uppercase;
            color: var(--rf20-primary);
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .rf20-title {
            font-size: 1.65rem;
            font-weight: 700;
            color: var(--rf20-text);
            margin-bottom: 0.3rem;
        }
        .rf20-subtitle {
            color: var(--rf20-text-soft);
            font-size: 0.96rem;
            line-height: 1.55;
            max-width: 52rem;
        }
        .rf20-section {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border);
            border-radius: 18px;
            padding: 1rem 1.05rem;
            margin-bottom: 0.9rem;
            box-shadow: var(--rf20-shadow);
        }
        .rf20-section.soft {
            background: var(--rf20-surface-soft);
        }
        .rf20-section.toned {
            background: var(--rf20-primary-soft);
            border-color: #CFE4DE;
        }
        .rf20-section-title {
            font-size: 0.92rem;
            font-weight: 700;
            color: var(--rf20-text);
            margin-bottom: 0.18rem;
        }
        .rf20-section-copy {
            font-size: 0.88rem;
            color: var(--rf20-text-soft);
            line-height: 1.5;
        }
        .rf20-panel {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border);
            border-radius: 16px;
            padding: 0.85rem 0.95rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 6px 18px rgba(16, 24, 40, 0.035);
        }
        .rf20-panel.soft {
            background: var(--rf20-surface-soft);
        }
        .rf20-panel.narrative {
            background: #F6FBFA;
            border-color: #D3E7E1;
        }
        .rf20-panel.recommendation {
            background: #FAFBF7;
            border-color: #D9E1D0;
        }
        .rf20-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
        }
        .rf20-heading {
            font-size: 1rem;
            font-weight: 700;
            color: var(--rf20-text);
            line-height: 1.3;
            margin-bottom: 0.1rem;
        }
        .rf20-kicker {
            color: var(--rf20-text-muted);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700;
        }
        .rf20-subline {
            color: var(--rf20-text-soft);
            font-size: 0.84rem;
            margin-top: 0.1rem;
        }
        .rf20-body {
            color: var(--rf20-text);
            font-size: 0.92rem;
            line-height: 1.5;
            margin-top: 0.45rem;
        }
        .rf20-meta-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.55rem;
            margin-top: 0.7rem;
        }
        .rf20-meta-item {
            background: var(--rf20-surface-soft);
            border: 1px solid var(--rf20-border);
            border-radius: 12px;
            padding: 0.55rem 0.7rem;
        }
        .rf20-meta-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--rf20-text-muted);
            font-weight: 700;
            margin-bottom: 0.18rem;
        }
        .rf20-meta-value {
            font-size: 0.9rem;
            color: var(--rf20-text);
            font-weight: 600;
            line-height: 1.3;
            word-break: break-word;
        }
        .rf20-summary-grid {
            display:grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap:0.65rem;
            margin-top:0.7rem;
        }
        .rf20-summary-card {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border);
            border-radius: 14px;
            padding: 0.75rem 0.85rem;
        }
        .rf20-summary-label {
            color: var(--rf20-text-muted);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700;
            margin-bottom: 0.18rem;
        }
        .rf20-summary-value {
            color: var(--rf20-text);
            font-size: 0.92rem;
            font-weight: 650;
            line-height: 1.35;
        }
        .rf20-inline-note {
            color: var(--rf20-text-soft);
            font-size: 0.85rem;
        }
        .rf20-soft {
            color: var(--rf20-text-soft);
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_home_header() -> None:
    inject_global_styles()
    st.markdown(
        f"""
        <div class="rf20-hero">
            <div class="rf20-eyebrow">Fraud Analytics</div>
            <div class="rf20-title">{APP_TITLE}</div>
            <div class="rf20-subtitle">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(*, title: str, subtitle: str, eyebrow: str = "RF20 Application Layer") -> None:
    inject_global_styles()
    st.markdown(
        f"""
        <div class="rf20-hero">
            <div class="rf20-eyebrow">{eyebrow}</div>
            <div class="rf20-title">{title}</div>
            <div class="rf20-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(*, title: str, subtitle: str | None = None, tone: str = "") -> None:
    tone_class = f" {tone}" if tone else ""
    subtitle_html = f'<div class="rf20-section-copy">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="rf20-section{tone_class}">
            <div class="rf20-section-title">{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
