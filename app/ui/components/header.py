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
            --rf20-bg: #F5F5F1;
            --rf20-surface: #FFFFFF;
            --rf20-surface-muted: #EEF2EF;
            --rf20-surface-narrative: #F7FBFA;
            --rf20-surface-reco: #FAFBF7;
            --rf20-border: #D4DDD8;
            --rf20-border-strong: #BECBC5;
            --rf20-text: #12302B;
            --rf20-text-soft: #4E625D;
            --rf20-text-muted: #70807B;
            --rf20-primary: #0F766E;
            --rf20-primary-ink: #0A5D57;
            --rf20-shadow: 0 10px 24px rgba(18, 48, 43, 0.045);
        }
        .stApp {
            background: var(--rf20-bg);
        }
        .block-container {
            max-width: 1120px;
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3, h4 {
            color: var(--rf20-text);
            letter-spacing: -0.02em;
        }
        .stMarkdown p {
            color: var(--rf20-text-soft);
            line-height: 1.58;
        }
        div[data-testid="stMetric"] {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            box-shadow: var(--rf20-shadow);
        }
        div[data-testid="stMetric"] label {
            color: var(--rf20-text-muted);
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700;
        }
        div[data-testid="stMetricValue"] {
            color: var(--rf20-text);
            font-size: 1.3rem;
            font-weight: 700;
        }
        div[data-baseweb="tab-list"] {
            gap: 0.45rem;
            margin-top: 0.25rem;
            margin-bottom: 0.9rem;
        }
        button[data-baseweb="tab"] {
            background: transparent;
            border-radius: 999px;
            padding: 0.28rem 0.8rem;
            border: 1px solid transparent;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: var(--rf20-surface);
            border-color: var(--rf20-border-strong);
        }
        div[data-testid="stExpander"] {
            border: 1px solid var(--rf20-border);
            border-radius: 16px;
            background: #F8F9F7;
        }
        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid var(--rf20-border);
        }
        .rf20-pagehead {
            padding: 0.2rem 0 0.8rem 0;
            border-bottom: 1px solid #DCE4E0;
            margin-bottom: 1.2rem;
        }
        .rf20-pagehead.hero {
            padding: 0.4rem 0 1.1rem 0;
            margin-bottom: 1.35rem;
        }
        .rf20-eyebrow {
            color: var(--rf20-primary);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
        }
        .rf20-title {
            color: var(--rf20-text);
            font-size: 1.9rem;
            line-height: 1.12;
            font-weight: 700;
            margin: 0 0 0.25rem 0;
        }
        .rf20-pagehead:not(.hero) .rf20-title {
            font-size: 1.6rem;
        }
        .rf20-subtitle {
            color: var(--rf20-text-soft);
            font-size: 0.98rem;
            max-width: 48rem;
            line-height: 1.55;
        }
        .rf20-lead {
            color: var(--rf20-text);
            font-size: 1.04rem;
            line-height: 1.6;
            max-width: 42rem;
            margin-top: 0.6rem;
        }
        .rf20-divider {
            border-top: 1px solid #DCE4E0;
            margin: 1.05rem 0 1rem 0;
        }
        .rf20-section-heading {
            margin: 0.2rem 0 0.7rem 0;
        }
        .rf20-section-title {
            color: var(--rf20-text);
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.12rem;
        }
        .rf20-section-copy {
            color: var(--rf20-text-soft);
            font-size: 0.9rem;
            line-height: 1.5;
            max-width: 52rem;
        }
        .rf20-callout {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border);
            border-radius: 18px;
            padding: 1rem 1.05rem;
            box-shadow: var(--rf20-shadow);
        }
        .rf20-callout.tight {
            padding: 0.85rem 0.95rem;
        }
        .rf20-summary-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.7rem;
            margin-top: 0.7rem;
        }
        .rf20-summary-item {
            padding-top: 0.2rem;
        }
        .rf20-summary-label {
            color: var(--rf20-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.7rem;
            font-weight: 700;
            margin-bottom: 0.1rem;
        }
        .rf20-summary-value {
            color: var(--rf20-text);
            font-size: 0.92rem;
            font-weight: 650;
            line-height: 1.35;
        }
        .rf20-list {
            background: var(--rf20-surface);
            border: 1px solid var(--rf20-border);
            border-radius: 16px;
            overflow: hidden;
        }
        .rf20-list-item {
            padding: 0.85rem 1rem;
            border-bottom: 1px solid #E3E9E5;
        }
        .rf20-list-item:last-child {
            border-bottom: 0;
        }
        .rf20-list-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.75rem;
        }
        .rf20-list-title {
            color: var(--rf20-text);
            font-size: 0.98rem;
            font-weight: 700;
            line-height: 1.3;
            margin-bottom: 0.08rem;
        }
        .rf20-list-subtitle {
            color: var(--rf20-text-soft);
            font-size: 0.85rem;
            line-height: 1.45;
        }
        .rf20-meta-line {
            color: var(--rf20-text-soft);
            font-size: 0.84rem;
            line-height: 1.45;
            margin-top: 0.45rem;
        }
        .rf20-meta-inline {
            color: var(--rf20-text);
            font-weight: 600;
        }
        .rf20-narrative {
            background: var(--rf20-surface-narrative);
            border-left: 3px solid #BFDCD6;
            padding: 0.8rem 1rem;
            border-radius: 0 14px 14px 0;
            margin-bottom: 0.75rem;
        }
        .rf20-recommendation {
            background: var(--rf20-surface-reco);
            border-left: 3px solid #D2DDBF;
            padding: 0.8rem 1rem;
            border-radius: 0 14px 14px 0;
            margin-bottom: 0.75rem;
        }
        .rf20-finding-item {
            background: #FBFCFB;
            border-left: 4px solid #BFDCD6;
        }
        .rf20-stepnav {
            display: flex;
            gap: 0.55rem;
            margin: 0.2rem 0 1rem 0;
            flex-wrap: wrap;
        }
        .rf20-stepchip {
            padding: 0.45rem 0.82rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            border: 1px solid var(--rf20-border);
            color: var(--rf20-text-soft);
            background: transparent;
        }
        .rf20-stepchip.active {
            background: var(--rf20-surface);
            color: var(--rf20-primary-ink);
            border-color: var(--rf20-border-strong);
        }
        .rf20-stepchip.done {
            background: #EDF7F5;
            color: var(--rf20-primary-ink);
            border-color: #CDE2DD;
        }
        .rf20-home-actions a {
            text-decoration: none;
        }
        .rf20-mini-note {
            color: var(--rf20-text-muted);
            font-size: 0.82rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_home_header() -> None:
    inject_global_styles()
    st.markdown(
        f"""
        <div class="rf20-pagehead hero">
            <div class="rf20-eyebrow">Fraud Analytics Workspace</div>
            <div class="rf20-title">{APP_TITLE}</div>
            <div class="rf20-subtitle">{APP_SUBTITLE}</div>
            <div class="rf20-lead">
                Sube un ERP controlado, decide el alcance del análisis y revisa hallazgos, explicaciones y recomendaciones
                con una experiencia pensada para investigación, no para navegar artefactos técnicos.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(*, title: str, subtitle: str, eyebrow: str = "ERP Fraud Analysis") -> None:
    inject_global_styles()
    st.markdown(
        f"""
        <div class="rf20-pagehead">
            <div class="rf20-eyebrow">{eyebrow}</div>
            <div class="rf20-title">{title}</div>
            <div class="rf20-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_heading(*, title: str, subtitle: str | None = None) -> None:
    subtitle_html = f'<div class="rf20-section-copy">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="rf20-section-heading">
            <div class="rf20-section-title">{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_divider() -> None:
    st.markdown('<div class="rf20-divider"></div>', unsafe_allow_html=True)
