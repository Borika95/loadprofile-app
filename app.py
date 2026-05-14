import os
import re
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from analysis import analyze_load_profile, read_load_profile
from circuit_tool import (
    LOCAL_EXTRACTION_VERSION,
    analyze_circuit_pdf,
    build_abc_analysis,
    classify_portfolio,
    consumers_to_dataframe,
    demo_circuit_result,
    prepare_portfolio_input,
)
from report import create_pdf_report
from email_service import send_pdf_report_email


st.set_page_config(
    page_title="Energieeffizienz Workspace",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    :root {
        --bg: #f6f8fb;
        --panel: #ffffff;
        --ink: #0f172a;
        --muted: #64748b;
        --line: #dbe4ee;
        --teal: #0f766e;
        --blue: #2563eb;
        --amber: #d97706;
        --red: #dc2626;
        --green: #15803d;
    }
    .stApp {
        background:
            linear-gradient(180deg, rgba(15, 118, 110, 0.08) 0%, rgba(246, 248, 251, 0) 320px),
            var(--bg);
        color: var(--ink);
    }
    .main .block-container {
        padding-top: 1.6rem;
        padding-bottom: 4rem;
        max-width: 1240px;
    }
    h1, h2, h3 {
        letter-spacing: 0;
    }
    a {
        text-decoration: none;
    }
    .workspace-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.7rem 0 1.15rem;
        color: var(--muted);
        font-size: 0.92rem;
    }
    .workspace-brand {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        color: var(--ink);
        font-weight: 800;
    }
    .workspace-mark {
        display: grid;
        place-items: center;
        width: 2rem;
        height: 2rem;
        border-radius: 8px;
        background: #0f172a;
        color: #ffffff;
        font-weight: 900;
    }
    .workspace-links {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    .workspace-links a,
    .sidebar-link {
        border: 1px solid var(--line);
        color: var(--ink);
        background: rgba(255, 255, 255, 0.78);
        border-radius: 8px;
        padding: 0.52rem 0.78rem;
        font-weight: 700;
        transition: border-color 160ms ease, background 160ms ease, color 160ms ease;
    }
    .workspace-links a:hover,
    .sidebar-link:hover {
        border-color: rgba(15, 118, 110, 0.45);
        background: #ffffff;
        color: var(--teal);
    }
    .landing-hero {
        display: grid;
        grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
        gap: 2rem;
        align-items: center;
        margin: 0.35rem 0 1.25rem;
        padding: 2.1rem;
        border-radius: 8px;
        background:
            linear-gradient(135deg, rgba(15, 118, 110, 0.97) 0%, rgba(37, 99, 235, 0.88) 58%, rgba(15, 23, 42, 0.98) 100%);
        box-shadow: 0 22px 58px rgba(15, 23, 42, 0.16);
        color: #ffffff;
        overflow: hidden;
    }
    .landing-hero h1 {
        color: #ffffff;
        font-size: clamp(2.35rem, 5vw, 4.55rem);
        line-height: 0.99;
        max-width: 900px;
        margin: 0 0 1rem;
    }
    .landing-hero p {
        color: rgba(255, 255, 255, 0.84);
        font-size: 1.05rem;
        line-height: 1.65;
        max-width: 760px;
        margin: 0;
    }
    .landing-preview {
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 8px;
        padding: 1rem;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
    }
    .preview-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        color: rgba(255, 255, 255, 0.82);
        font-size: 0.8rem;
        font-weight: 800;
        margin-bottom: 0.8rem;
    }
    .preview-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.55rem;
        margin-bottom: 0.8rem;
    }
    .preview-kpi {
        background: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 8px;
        padding: 0.65rem;
    }
    .preview-kpi b {
        display: block;
        color: #ffffff;
        font-size: 1.18rem;
        line-height: 1.1;
    }
    .preview-kpi span {
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.72rem;
        font-weight: 700;
    }
    .preview-chart {
        display: flex;
        align-items: flex-end;
        gap: 0.42rem;
        height: 120px;
        padding: 0.85rem;
        background: rgba(15, 23, 42, 0.28);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.14);
    }
    .preview-bar {
        flex: 1;
        min-width: 16px;
        border-radius: 6px 6px 0 0;
        background: linear-gradient(180deg, #ffffff, #7dd3fc);
        opacity: 0.92;
    }
    .preview-bar.teal {
        background: linear-gradient(180deg, #ccfbf1, #0d9488);
    }
    .preview-foot {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.55rem;
        margin-top: 0.8rem;
    }
    .preview-chip {
        background: rgba(255, 255, 255, 0.13);
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 8px;
        color: rgba(255, 255, 255, 0.84);
        padding: 0.55rem 0.65rem;
        font-size: 0.8rem;
        font-weight: 800;
    }
    .landing-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
        margin-top: 1.25rem;
    }
    .meta-pill {
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.12);
        color: rgba(255, 255, 255, 0.88);
        padding: 0.48rem 0.72rem;
        font-size: 0.88rem;
        font-weight: 700;
    }
    .app-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1rem;
        margin: 1.7rem 0 1rem;
    }
    .app-card {
        position: relative;
        display: flex;
        min-height: 285px;
        overflow: hidden;
        border-radius: 8px;
        border: 1px solid rgba(15, 118, 110, 0.24);
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        box-shadow:
            0 24px 56px rgba(15, 23, 42, 0.13),
            0 0 0 1px rgba(255, 255, 255, 0.72) inset;
        color: var(--ink);
        transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
    }
    .app-card::after {
        content: "";
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 5px;
        background: linear-gradient(90deg, #0f766e, #2563eb);
        opacity: 0.92;
    }
    .app-card:hover {
        transform: translateY(-5px);
        box-shadow:
            0 30px 68px rgba(15, 23, 42, 0.18),
            0 0 0 1px rgba(255, 255, 255, 0.82) inset;
        border-color: rgba(15, 118, 110, 0.58);
    }
    .app-card:focus {
        outline: 3px solid rgba(37, 99, 235, 0.24);
        outline-offset: 3px;
    }
    .app-card-content {
        position: relative;
        z-index: 2;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        width: 100%;
        padding: 1.25rem;
    }
    .app-card-accent {
        position: absolute;
        inset: 0;
        opacity: 0.92;
    }
    .app-card-accent.load {
        background:
            linear-gradient(145deg, rgba(15, 118, 110, 0.18), rgba(37, 99, 235, 0.08)),
            linear-gradient(105deg, transparent 0 58%, rgba(37, 99, 235, 0.1) 58% 75%, transparent 75%),
            #ffffff;
    }
    .app-card-accent.catalog {
        background:
            linear-gradient(145deg, rgba(15, 118, 110, 0.18), rgba(37, 99, 235, 0.08)),
            linear-gradient(105deg, transparent 0 55%, rgba(13, 148, 136, 0.12) 55% 74%, transparent 74%),
            #ffffff;
    }
    .app-card-accent.circuit {
        background:
            linear-gradient(145deg, rgba(15, 118, 110, 0.16), rgba(15, 23, 42, 0.08)),
            linear-gradient(105deg, transparent 0 52%, rgba(37, 99, 235, 0.12) 52% 70%, transparent 70%),
            #ffffff;
    }
    .app-card-kicker {
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 900;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .app-card h2 {
        max-width: 520px;
        margin: 0.55rem 0 0;
        color: var(--ink);
        font-size: clamp(1.55rem, 3vw, 2.45rem);
        line-height: 1.04;
    }
    .app-card-description {
        max-width: 560px;
        color: var(--muted);
        line-height: 1.55;
        opacity: 1;
        transform: none;
        transition: opacity 180ms ease, transform 180ms ease;
    }
    .app-card:hover .app-card-description,
    .app-card:focus .app-card-description {
        opacity: 1;
        transform: translateY(0);
    }
    .app-card-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        color: var(--ink);
        font-weight: 800;
    }
    .app-card-signal {
        display: grid;
        place-items: center;
        width: 2.6rem;
        height: 2.6rem;
        border-radius: 8px;
        background: rgba(15, 23, 42, 0.92);
        color: white;
        font-size: 1.2rem;
    }
    .app-card-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.85rem;
    }
    .app-card-metric {
        border: 1px solid rgba(15, 118, 110, 0.18);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.72);
        color: var(--muted);
        padding: 0.36rem 0.5rem;
        font-size: 0.76rem;
        font-weight: 800;
    }
    .hero {
        background:
            linear-gradient(135deg, rgba(15, 118, 110, 0.95) 0%, rgba(37, 99, 235, 0.92) 58%, rgba(15, 23, 42, 0.95) 100%);
        padding: 1.8rem 1.9rem;
        border-radius: 8px;
        color: white;
        box-shadow: 0 18px 44px rgba(15, 23, 42, 0.12);
        margin-bottom: 1.6rem;
    }
    .hero h1 {
        font-size: 2.2rem;
        margin-bottom: 0.45rem;
        line-height: 1.08;
    }
    .hero p {
        color: rgba(255, 255, 255, 0.84);
        font-size: 1.05rem;
        max-width: 840px;
    }
    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-top: 1.2rem;
    }
    .badge {
        background: rgba(255, 255, 255, 0.13);
        border: 1px solid rgba(255, 255, 255, 0.20);
        color: white;
        padding: 0.42rem 0.72rem;
        border-radius: 8px;
        font-size: 0.86rem;
    }
    .page-header {
        background:
            linear-gradient(135deg, rgba(15, 118, 110, 0.96) 0%, rgba(37, 99, 235, 0.9) 58%, rgba(15, 23, 42, 0.96) 100%);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 8px;
        padding: 1.35rem 1.45rem;
        box-shadow: 0 18px 44px rgba(15, 23, 42, 0.13);
        margin-bottom: 1rem;
        color: #ffffff;
    }
    .page-header h1 {
        margin: 0.15rem 0 0.45rem;
        font-size: 2.05rem;
        line-height: 1.12;
        color: #ffffff;
    }
    .page-header p {
        color: rgba(255, 255, 255, 0.84);
        max-width: 880px;
        line-height: 1.55;
        margin: 0;
    }
    .eyebrow {
        color: rgba(255, 255, 255, 0.78);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 900;
        font-size: 0.78rem;
    }
    .section-card {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1.35rem 1.45rem;
        box-shadow: 0 14px 32px rgba(15, 23, 42, 0.055);
        margin-bottom: 1rem;
        color: var(--ink);
    }
    .section-card h1,
    .section-card h2,
    .section-card h3,
    .section-card p,
    .section-card label,
    .section-card span,
    .section-card div {
        color: var(--ink);
    }
    .section-card [data-testid="stMarkdownContainer"] p,
    .section-card [data-testid="stCaptionContainer"],
    .section-card [data-testid="stWidgetLabel"],
    .section-card [data-testid="stWidgetLabel"] p,
    .section-card [data-baseweb="select"] div,
    .section-card input,
    .section-card textarea {
        color: var(--ink) !important;
    }
    .section-card input::placeholder,
    .section-card textarea::placeholder {
        color: var(--muted) !important;
    }
    .section-card div[data-baseweb="select"] {
        background: #ffffff;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.85rem 0.95rem;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.045);
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] label p,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"],
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
        color: var(--muted) !important;
        font-weight: 800 !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"],
    div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
        color: var(--ink) !important;
        font-weight: 900 !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: var(--teal) !important;
    }
    .insight {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #0f766e;
        border-radius: 8px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }
    .recommendation-high { border-left: 5px solid #dc2626; }
    .recommendation-medium { border-left: 5px solid #f59e0b; }
    .recommendation-low { border-left: 5px solid #0f766e; }
    .small-muted {
        color: #64748b;
        font-size: 0.92rem;
    }
    div[data-testid="stProgress"] > div > div > div > div {
        background-color: #0f766e;
    }
    .measure-card {
        background: rgba(255, 255, 255, 0.86);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1rem 1.05rem;
        margin: 0 0 0.85rem;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.045);
    }
    .measure-card h3 {
        margin: 0 0 0.45rem;
        font-size: 1.08rem;
    }
    .measure-card p {
        color: var(--muted);
        line-height: 1.52;
        margin: 0.4rem 0 0.75rem;
    }
    .measure-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
    }
    .measure-chip {
        border-radius: 8px;
        padding: 0.32rem 0.5rem;
        border: 1px solid var(--line);
        color: var(--muted);
        background: #ffffff;
        font-size: 0.78rem;
        font-weight: 800;
    }
    .chip-high {
        border-color: rgba(220, 38, 38, 0.28);
        color: var(--red);
        background: rgba(220, 38, 38, 0.07);
    }
    .chip-medium {
        border-color: rgba(217, 119, 6, 0.28);
        color: var(--amber);
        background: rgba(217, 119, 6, 0.08);
    }
    .chip-low {
        border-color: rgba(21, 128, 61, 0.26);
        color: var(--green);
        background: rgba(21, 128, 61, 0.07);
    }
    .workflow-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
    }
    .workflow-step {
        background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.9));
        border: 1px solid rgba(15, 118, 110, 0.18);
        border-top: 4px solid rgba(15, 118, 110, 0.72);
        border-radius: 8px;
        padding: 0.95rem 1rem;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.055);
    }
    .workflow-step b {
        display: block;
        color: var(--ink);
        margin-bottom: 0.28rem;
    }
    .workflow-step span {
        color: var(--muted);
        line-height: 1.45;
        font-size: 0.92rem;
    }
    .result-summary {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
    }
    .summary-card {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.9rem 1rem;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.055);
    }
    .summary-card span {
        display: block;
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .summary-card b {
        display: block;
        color: var(--ink);
        font-size: 1.55rem;
        line-height: 1.15;
        margin-top: 0.28rem;
    }
    .summary-card em {
        display: block;
        color: var(--teal);
        font-style: normal;
        font-size: 0.82rem;
        font-weight: 800;
        margin-top: 0.35rem;
    }
    .insight-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 0.9rem 0 1rem;
    }
    .insight-tile {
        background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.92));
        border: 1px solid rgba(15, 118, 110, 0.16);
        border-left: 5px solid #0f766e;
        border-radius: 8px;
        padding: 0.85rem 0.95rem;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.045);
    }
    .insight-tile b {
        display: block;
        color: var(--ink);
        margin-bottom: 0.25rem;
    }
    .insight-tile span {
        color: var(--muted);
        line-height: 1.45;
        font-size: 0.9rem;
    }
    div[data-baseweb="tab-list"] {
        gap: 0.45rem;
        border-bottom: 1px solid var(--line);
        margin-top: 0.4rem;
    }
    button[data-baseweb="tab"] {
        background: #ffffff !important;
        border: 1px solid var(--line) !important;
        border-bottom: none !important;
        border-radius: 8px 8px 0 0 !important;
        color: var(--ink) !important;
        padding: 0.55rem 0.8rem !important;
    }
    button[data-baseweb="tab"] p,
    button[data-baseweb="tab"] span {
        color: var(--ink) !important;
        font-weight: 800 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #0f766e, #2563eb) !important;
        border-color: #0f766e !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p,
    button[data-baseweb="tab"][aria-selected="true"] span {
        color: #ffffff !important;
    }
    .sidebar-nav {
        display: grid;
        gap: 0.4rem;
        margin-bottom: 1rem;
    }
    .sidebar-link {
        display: block;
    }
    .sidebar-link.active {
        border-color: rgba(15, 118, 110, 0.48);
        color: var(--teal);
        background: #ffffff;
    }
    .stButton > button {
        border-radius: 8px;
        border: none;
        background: linear-gradient(135deg, #0f766e, #0d9488);
        color: white;
        padding: 0.7rem 1.3rem;
        font-weight: 700;
        box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
    }
    .stDownloadButton > button {
        border-radius: 8px;
        background: #0f766e;
        color: white;
        font-weight: 700;
        border: none;
        padding: 0.7rem 1.2rem;
    }
    @media (max-width: 860px) {
        .workspace-topbar {
            align-items: flex-start;
            flex-direction: column;
        }
        .app-grid {
            grid-template-columns: 1fr;
        }
        .workflow-strip {
            grid-template-columns: 1fr;
        }
        .landing-hero,
        .result-summary,
        .insight-strip {
            grid-template-columns: 1fr;
        }
        .app-card {
            min-height: 250px;
        }
        .app-card-description {
            opacity: 1;
            transform: none;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


APP_ROUTES = {
    "home": "Workspace",
    "load-analysis": "Lastganganalyse",
    "measures-catalog": "Maßnahmenkatalog",
    "circuit-tool": "Schaltplantool",
}


MEASURE_CATALOG = [
    {
        "id": "standby-shutdown",
        "title": "Abschaltmatrix für Nebenaggregate",
        "area": "Grundlast",
        "priority": "hoch",
        "effort": "mittel",
        "investment": "niedrig",
        "payback_months": 6,
        "savings_pct": 7.5,
        "owner": "Produktion / Instandhaltung",
        "description": "Standby-Verbraucher, Absaugungen, Pumpen und Temperierungen werden nach Schichtende gezielt abgeschaltet.",
    },
    {
        "id": "compressed-air-leakage",
        "title": "Druckluft-Leckageprogramm",
        "area": "Druckluft",
        "priority": "hoch",
        "effort": "mittel",
        "investment": "niedrig",
        "payback_months": 5,
        "savings_pct": 8.0,
        "owner": "Instandhaltung",
        "description": "Leckagen werden zyklisch erfasst, priorisiert und mit Zuständigkeiten in die Wartungsroutine überführt.",
    },
    {
        "id": "peak-load-sequencing",
        "title": "Startsequenzen gegen Lastspitzen",
        "area": "Lastspitzen",
        "priority": "hoch",
        "effort": "mittel",
        "investment": "niedrig",
        "payback_months": 4,
        "savings_pct": 4.5,
        "owner": "Produktion / Energiemanagement",
        "description": "Energieintensive Anlagen werden zeitversetzt angefahren, damit Leistungspreise und Netzspitzen sinken.",
    },
    {
        "id": "vfd-pumps-fans",
        "title": "Drehzahlregelung für Pumpen und Ventilatoren",
        "area": "Antriebe",
        "priority": "mittel",
        "effort": "hoch",
        "investment": "mittel",
        "payback_months": 18,
        "savings_pct": 9.0,
        "owner": "Technik",
        "description": "Ungeregelte Antriebe werden auf bedarfsgerechte Fahrweise geprüft und bei hoher Laufzeit priorisiert.",
    },
    {
        "id": "machine-metering",
        "title": "Maschinennahe Energiezähler",
        "area": "Monitoring",
        "priority": "mittel",
        "effort": "mittel",
        "investment": "mittel",
        "payback_months": 14,
        "savings_pct": 3.5,
        "owner": "Energiemanagement / IT",
        "description": "Relevante Linien werden messbar, damit Energie je Produkt, Charge oder Schicht belastbar verfolgt wird.",
    },
    {
        "id": "heat-recovery",
        "title": "Abwärmenutzung an Kompressoren",
        "area": "Wärme",
        "priority": "mittel",
        "effort": "hoch",
        "investment": "hoch",
        "payback_months": 28,
        "savings_pct": 6.0,
        "owner": "Technik / Gebäude",
        "description": "Kompressorabwärme wird für Raumwärme, Prozesswärme oder Warmwasser nutzbar gemacht.",
    },
    {
        "id": "lighting-zones",
        "title": "Zonenbasierte LED- und Präsenzsteuerung",
        "area": "Beleuchtung",
        "priority": "niedrig",
        "effort": "mittel",
        "investment": "mittel",
        "payback_months": 24,
        "savings_pct": 2.5,
        "owner": "Facility Management",
        "description": "Beleuchtung wird nach Hallenbereich, Nutzung und Tageslicht gesteuert statt pauschal betrieben.",
    },
    {
        "id": "cooling-setpoints",
        "title": "Kälte- und Temperiersollwerte optimieren",
        "area": "Kälte",
        "priority": "mittel",
        "effort": "niedrig",
        "investment": "niedrig",
        "payback_months": 3,
        "savings_pct": 4.0,
        "owner": "Produktion / Qualität",
        "description": "Sollwerte, Hysterese und Betriebsfenster werden so eingestellt, dass Qualität und Energiebedarf zusammenpassen.",
    },
    {
        "id": "maintenance-energy",
        "title": "Energiecheck in Wartungspläne integrieren",
        "area": "Organisation",
        "priority": "niedrig",
        "effort": "niedrig",
        "investment": "niedrig",
        "payback_months": 8,
        "savings_pct": 2.0,
        "owner": "Instandhaltung",
        "description": "Filter, Lager, Druckniveaus, Isolierung und Leerlaufzeiten werden als feste Energiepunkte mitgeprüft.",
    },
    {
        "id": "shift-energy-dashboard",
        "title": "Schicht-Dashboard für Energiekennzahlen",
        "area": "Monitoring",
        "priority": "mittel",
        "effort": "mittel",
        "investment": "niedrig",
        "payback_months": 10,
        "savings_pct": 3.0,
        "owner": "Produktion / Controlling",
        "description": "Teams sehen Energie je Schicht, Stück und Linie und können Abweichungen direkt im Shopfloor-Meeting besprechen.",
    },
]


PRIORITY_ORDER = {"hoch": 0, "mittel": 1, "niedrig": 2}


def app_href(app_id: str) -> str:
    return "?app=home" if app_id == "home" else f"?app={app_id}"


def get_active_app() -> str:
    requested_app = st.query_params.get("app", "home")
    if isinstance(requested_app, list):
        requested_app = requested_app[0] if requested_app else "home"
    return requested_app if requested_app in APP_ROUTES else "home"


def render_workspace_topbar(active_app: str):
    active_label = APP_ROUTES.get(active_app, APP_ROUTES["home"])
    st.markdown(
        f"""
        <div class="workspace-topbar">
            <a class="workspace-brand" href="{app_href('home')}" target="_self">
                <span class="workspace-mark">E</span>
                <span>Energieeffizienz Workspace</span>
            </a>
            <div class="workspace-links">
                <a href="{app_href('home')}" target="_self">Workspace</a>
                <a href="{app_href('load-analysis')}" target="_self">Lastganganalyse</a>
                <a href="{app_href('measures-catalog')}" target="_self">Maßnahmenkatalog</a>
                <a href="{app_href('circuit-tool')}" target="_self">Schaltplantool</a>
            </div>
        </div>
        <div class="small-muted">Aktive Anwendung: <b>{active_label}</b></div>
        """,
        unsafe_allow_html=True,
    )


def render_app_sidebar(active_app: str):
    home_active = " active" if active_app == "home" else ""
    analysis_active = " active" if active_app == "load-analysis" else ""
    catalog_active = " active" if active_app == "measures-catalog" else ""
    circuit_active = " active" if active_app == "circuit-tool" else ""

    with st.sidebar:
        st.markdown("### Anwendungen")
        st.markdown(
            f"""
            <div class="sidebar-nav">
                <a class="sidebar-link{home_active}" href="{app_href('home')}" target="_self">Workspace</a>
                <a class="sidebar-link{analysis_active}" href="{app_href('load-analysis')}" target="_self">Lastganganalyse</a>
                <a class="sidebar-link{catalog_active}" href="{app_href('measures-catalog')}" target="_self">Maßnahmenkatalog</a>
                <a class="sidebar-link{circuit_active}" href="{app_href('circuit-tool')}" target="_self">Schaltplantool</a>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_landing_page():
    render_workspace_topbar("home")
    st.markdown(
        f"""
        <section class="landing-hero">
            <div>
                <h1>Energieentscheidungen vom Signal bis zur Messstelle.</h1>
                <p>
                    Ein Workspace für Lastgang-Analyse, Maßnahmenpriorisierung und KI-gestützte
                    Schaltplanauswertung: gebaut für schnelle Energie-Transparenz in der Produktion.
                </p>
                <div class="landing-meta">
                    <span class="meta-pill">3 Unteranwendungen</span>
                    <span class="meta-pill">Analyse bis Maßnahmenplan</span>
                    <span class="meta-pill">Pitchfähiger Demo-Flow</span>
                </div>
            </div>
            <div class="landing-preview">
                <div class="preview-header">
                    <span>ENERGIEEFFIZIENZ DASHBOARD</span>
                    <span>LIVE DEMO</span>
                </div>
                <div class="preview-grid">
                    <div class="preview-kpi"><b>21.4</b><span>MWh Einsparpotenzial</span></div>
                    <div class="preview-kpi"><b>7</b><span>erkannte Verbraucher</span></div>
                    <div class="preview-kpi"><b>A/B</b><span>Messpriorität</span></div>
                </div>
                <div class="preview-chart">
                    <span class="preview-bar teal" style="height: 82%"></span>
                    <span class="preview-bar" style="height: 48%"></span>
                    <span class="preview-bar teal" style="height: 68%"></span>
                    <span class="preview-bar" style="height: 36%"></span>
                    <span class="preview-bar teal" style="height: 92%"></span>
                    <span class="preview-bar" style="height: 58%"></span>
                    <span class="preview-bar teal" style="height: 74%"></span>
                </div>
                <div class="preview-foot">
                    <span class="preview-chip">ABC-Analyse</span>
                    <span class="preview-chip">Energieportfolio</span>
                </div>
            </div>
        </section>

        <section class="app-grid">
            <a class="app-card" href="{app_href('load-analysis')}" target="_self">
                <span class="app-card-accent load"></span>
                <div class="app-card-content">
                    <div>
                        <span class="app-card-kicker">Analyse</span>
                        <h2>Lastganganalyse</h2>
                    </div>
                    <p class="app-card-description">
                        Produktions- und Energiedaten erfassen, Lastgänge hochladen, Kennzahlen berechnen
                        und priorisierte Einsparpotenziale als Bericht vorbereiten.
                    </p>
                    <div class="app-card-metrics">
                        <span class="app-card-metric">Grundlast</span>
                        <span class="app-card-metric">Lastspitzen</span>
                        <span class="app-card-metric">PDF-Bericht</span>
                    </div>
                    <div class="app-card-footer">
                        <span>Anwendung öffnen</span>
                        <span class="app-card-signal">LA</span>
                    </div>
                </div>
            </a>
            <a class="app-card" href="{app_href('measures-catalog')}" target="_self">
                <span class="app-card-accent catalog"></span>
                <div class="app-card-content">
                    <div>
                        <span class="app-card-kicker">Umsetzung</span>
                        <h2>Interaktiver Maßnahmenkatalog</h2>
                    </div>
                    <p class="app-card-description">
                        Maßnahmen nach Bereich, Priorität, Aufwand und Amortisation filtern,
                        Favoriten merken und einen ersten Maßnahmenplan exportieren.
                    </p>
                    <div class="app-card-metrics">
                        <span class="app-card-metric">Filter</span>
                        <span class="app-card-metric">Priorität</span>
                        <span class="app-card-metric">CSV-Export</span>
                    </div>
                    <div class="app-card-footer">
                        <span>Anwendung öffnen</span>
                        <span class="app-card-signal">MK</span>
                    </div>
                </div>
            </a>
            <a class="app-card" href="{app_href('circuit-tool')}" target="_self">
                <span class="app-card-accent circuit"></span>
                <div class="app-card-content">
                    <div>
                        <span class="app-card-kicker">Schaltpläne</span>
                        <h2>KI-Schaltplantool</h2>
                    </div>
                    <p class="app-card-description">
                        Elektrische Schaltplan-PDFs hochladen, Verbraucher mit Metadaten extrahieren
                        und über ABC-Analyse, Energieportfolio und Tabelle priorisieren.
                    </p>
                    <div class="app-card-metrics">
                        <span class="app-card-metric">PDF/KI</span>
                        <span class="app-card-metric">ABC</span>
                        <span class="app-card-metric">Portfolio</span>
                    </div>
                    <div class="app-card-footer">
                        <span>Anwendung öffnen</span>
                        <span class="app-card-signal">ST</span>
                    </div>
                </div>
            </a>
        </section>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    defaults = {
        "step": 1,
        "company_data": {},
        "production_data": {},
        "energy_data": {},
        "process_data": {},
        "analysis": None,
        "df": None,
        "email": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def next_step():
    st.session_state.step = min(st.session_state.step + 1, 6)


def previous_step():
    st.session_state.step = max(st.session_state.step - 1, 1)


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def priority_chip_class(priority: str) -> str:
    return {
        "hoch": "chip-high",
        "mittel": "chip-medium",
        "niedrig": "chip-low",
    }.get(priority, "chip-low")


def filter_measures(
    search: str,
    selected_areas: list[str],
    selected_priorities: list[str],
    selected_efforts: list[str],
    max_payback: int,
) -> list[dict]:
    search_normalized = search.strip().lower()
    results = []

    for measure in MEASURE_CATALOG:
        searchable = " ".join(
            [
                measure["title"],
                measure["area"],
                measure["priority"],
                measure["effort"],
                measure["investment"],
                measure["owner"],
                measure["description"],
            ]
        ).lower()
        if search_normalized and search_normalized not in searchable:
            continue
        if selected_areas and measure["area"] not in selected_areas:
            continue
        if selected_priorities and measure["priority"] not in selected_priorities:
            continue
        if selected_efforts and measure["effort"] not in selected_efforts:
            continue
        if measure["payback_months"] > max_payback:
            continue
        results.append(measure)

    return results


def sort_measures(measures: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "Amortisation":
        return sorted(measures, key=lambda item: item["payback_months"])
    if sort_by == "Einsparpotenzial":
        return sorted(measures, key=lambda item: item["savings_pct"], reverse=True)
    return sorted(measures, key=lambda item: (PRIORITY_ORDER[item["priority"]], item["payback_months"]))


def render_measure_card(measure: dict) -> bool:
    chip_class = priority_chip_class(measure["priority"])
    st.markdown(
        f"""
        <div class="measure-card">
            <h3>{measure['title']}</h3>
            <div class="measure-meta">
                <span class="measure-chip">{measure['area']}</span>
                <span class="measure-chip {chip_class}">Priorität: {measure['priority']}</span>
                <span class="measure-chip">Aufwand: {measure['effort']}</span>
                <span class="measure-chip">Invest: {measure['investment']}</span>
                <span class="measure-chip">{measure['payback_months']} Monate</span>
                <span class="measure-chip">{measure['savings_pct']:.1f} % Potenzial</span>
            </div>
            <p>{measure['description']}</p>
            <div class="small-muted">Owner: <b>{measure['owner']}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.checkbox("In Maßnahmenplan aufnehmen", key=f"measure_selected_{measure['id']}")


def render_measures_catalog_app():
    render_workspace_topbar("measures-catalog")
    render_app_sidebar("measures-catalog")

    area_options = sorted({measure["area"] for measure in MEASURE_CATALOG})
    priority_options = ["hoch", "mittel", "niedrig"]
    effort_options = ["niedrig", "mittel", "hoch"]

    with st.sidebar:
        st.subheader("Katalog filtern")
        search = st.text_input("Suche", placeholder="z. B. Druckluft, Grundlast, Monitoring")
        selected_areas = st.multiselect("Bereiche", area_options, default=area_options)
        selected_priorities = st.multiselect("Priorität", priority_options, default=priority_options)
        selected_efforts = st.multiselect("Aufwand", effort_options, default=effort_options)
        max_payback = st.slider("Amortisation bis [Monate]", min_value=3, max_value=36, value=36, step=1)
        sort_by = st.selectbox("Sortierung", ["Priorität", "Amortisation", "Einsparpotenzial"])

    st.markdown(
        """
        <div class="page-header">
            <div class="eyebrow">Interaktiver Maßnahmenkatalog</div>
            <h1>Maßnahmen filtern, bewerten und vormerken</h1>
            <p>
                Der Katalog übersetzt Analyseergebnisse in konkrete Ansatzpunkte für Produktion,
                Instandhaltung, Facility Management und Energiemanagement.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    filtered_measures = sort_measures(
        filter_measures(search, selected_areas, selected_priorities, selected_efforts, max_payback),
        sort_by,
    )

    m1, m2, m3, m4 = st.columns(4)
    high_priority_count = sum(1 for measure in filtered_measures if measure["priority"] == "hoch")
    avg_payback = (
        sum(measure["payback_months"] for measure in filtered_measures) / len(filtered_measures)
        if filtered_measures
        else 0
    )
    max_savings = max((measure["savings_pct"] for measure in filtered_measures), default=0)
    m1.metric("Treffer", len(filtered_measures))
    m2.metric("Hohe Priorität", high_priority_count)
    m3.metric("Ø Amortisation", f"{avg_payback:.0f} Monate")
    m4.metric("Max. Potenzial", f"{max_savings:.1f} %")

    catalog_tab, plan_tab = st.tabs(["Katalog", "Maßnahmenplan"])

    with catalog_tab:
        if not filtered_measures:
            st.info("Für die gewählten Filter wurden keine Maßnahmen gefunden.")
        for measure in filtered_measures:
            render_measure_card(measure)

    selected_measures = [
        measure for measure in MEASURE_CATALOG if st.session_state.get(f"measure_selected_{measure['id']}", False)
    ]

    with plan_tab:
        if not selected_measures:
            st.info("Noch keine Maßnahmen im Plan.")
        else:
            plan_df = pd.DataFrame(selected_measures)[
                ["title", "area", "priority", "effort", "investment", "payback_months", "savings_pct", "owner"]
            ].rename(
                columns={
                    "title": "Maßnahme",
                    "area": "Bereich",
                    "priority": "Priorität",
                    "effort": "Aufwand",
                    "investment": "Invest",
                    "payback_months": "Amortisation [Monate]",
                    "savings_pct": "Potenzial [%]",
                    "owner": "Owner",
                }
            )
            st.dataframe(plan_df, width="stretch", hide_index=True)
            st.download_button(
                "Maßnahmenplan als CSV exportieren",
                data=plan_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="massnahmenplan.csv",
                mime="text/csv",
            )


def get_openai_api_key() -> str | None:
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_API_KEY")

    try:
        direct_key = st.secrets.get("OPENAI_API_KEY")
        if direct_key:
            return direct_key
        openai_config = st.secrets.get("openai", {})
        return openai_config.get("api_key") or openai_config.get("OPENAI_API_KEY")
    except Exception:
        return None


def render_abc_chart(abc_df: pd.DataFrame, a_limit: float, b_limit: float):
    if abc_df.empty:
        st.info("Für die ABC-Analyse fehlen Verbraucher mit Nennleistung.")
        return

    df = abc_df.copy().reset_index(drop=True)
    df["order_idx"] = df.index
    df["nominal_power_kw"] = pd.to_numeric(df["nominal_power_kw"], errors="coerce").fillna(0)
    df["label"] = [
        row.identifier or str(row.designation)[:22]
        for row in df.itertuples()
    ]
    df["tooltip_power"] = df["nominal_power_kw"].map(lambda value: f"{value:.2f} kW")
    df["tooltip_share"] = df["share_power_pct"].map(lambda value: f"{value:.1f} %")
    df["tooltip_cum"] = df["cum_power_pct"].map(lambda value: f"{value:.1f} %")

    hover = alt.selection_point(fields=["label"], on="pointerover", nearest=True, empty=False)
    group_scale = alt.Scale(domain=["A", "B", "C"], range=["#0f766e", "#2563eb", "#64748b"])
    x_axis = alt.X(
        "label:N",
        sort=alt.SortField("order_idx", order="ascending"),
        title=None,
        axis=alt.Axis(labelAngle=-28, labelLimit=110),
    )
    tooltip = [
        alt.Tooltip("detection_id:Q", title="ID"),
        alt.Tooltip("page:Q", title="Seite"),
        alt.Tooltip("identifier:N", title="Kennzeichen"),
        alt.Tooltip("designation:N", title="Bezeichnung"),
        alt.Tooltip("consumer_type:N", title="Typ"),
        alt.Tooltip("tooltip_power:N", title="Nennleistung"),
        alt.Tooltip("tooltip_share:N", title="Leistungsanteil"),
        alt.Tooltip("tooltip_cum:N", title="Kumuliert"),
        alt.Tooltip("abc_group:N", title="ABC"),
    ]

    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=x_axis,
            y=alt.Y("nominal_power_kw:Q", title="Nennleistung [kW]", axis=alt.Axis(titleColor="#334155")),
            color=alt.Color("abc_group:N", title="ABC", scale=group_scale),
            opacity=alt.condition(hover, alt.value(1), alt.value(0.72)),
            tooltip=tooltip,
        )
    )

    cumulative_line = (
        alt.Chart(df)
        .mark_line(point=alt.OverlayMarkDef(size=78, filled=True), color="#0f172a", strokeWidth=2.5)
        .encode(
            x=x_axis,
            y=alt.Y(
                "cum_power_pct:Q",
                title="Kumulierte Leistung [%]",
                scale=alt.Scale(domain=[0, 105]),
                axis=alt.Axis(orient="right", titleColor="#0f172a"),
            ),
            tooltip=tooltip,
        )
    )

    threshold_df = pd.DataFrame(
        [
            {"threshold": a_limit, "name": "A-Grenze"},
            {"threshold": b_limit, "name": "B-Grenze"},
        ]
    )
    thresholds = (
        alt.Chart(threshold_df)
        .mark_rule(strokeDash=[6, 5], strokeWidth=1.2)
        .encode(
            y=alt.Y("threshold:Q", scale=alt.Scale(domain=[0, 105])),
            color=alt.Color("name:N", title=None, scale=alt.Scale(domain=["A-Grenze", "B-Grenze"], range=["#0f766e", "#2563eb"])),
            tooltip=[alt.Tooltip("name:N", title="Grenze"), alt.Tooltip("threshold:Q", title="Wert [%]", format=".0f")],
        )
    )

    chart = (
        alt.layer(bars, cumulative_line + thresholds)
        .add_params(hover)
        .resolve_scale(y="independent")
        .properties(height=390)
        .configure_axis(gridColor="#e2e8f0", labelColor="#475569", titleColor="#334155")
        .configure_view(strokeWidth=0)
        .interactive(bind_y=False)
    )
    st.altair_chart(chart, use_container_width=True)


def render_portfolio_plot(portfolio_df: pd.DataFrame, utilization_threshold: float, time_threshold: float):
    if portfolio_df.empty:
        st.info("Für das Energieportfolio fehlen Verbraucher.")
        return

    df = portfolio_df.copy()
    df["nominal_power_kw"] = pd.to_numeric(df["nominal_power_kw"], errors="coerce").fillna(0)
    df["utilization_pct"] = pd.to_numeric(df["utilization_pct"], errors="coerce").fillna(50).clip(0, 100)
    df["operating_time_pct"] = pd.to_numeric(df["operating_time_pct"], errors="coerce").fillna(50).clip(0, 100)
    df["label"] = [row.identifier or str(row.designation)[:16] for row in df.itertuples()]
    df["tooltip_power"] = df["nominal_power_kw"].map(lambda value: f"{value:.2f} kW" if value > 0 else "unbekannt")
    df["tooltip_utilization"] = df["utilization_pct"].map(lambda value: f"{value:.0f} %")
    df["tooltip_time"] = df["operating_time_pct"].map(lambda value: f"{value:.0f} %")
    df["bubble_power_kw"] = df["nominal_power_kw"].clip(lower=0.1)

    quadrant_df = pd.DataFrame(
        [
            {"portfolio_class": "I", "x": time_threshold, "x2": 100, "y": utilization_threshold, "y2": 100, "label_x": (time_threshold + 100) / 2, "label_y": 88, "name": "Klasse I"},
            {"portfolio_class": "II", "x": 0, "x2": time_threshold, "y": utilization_threshold, "y2": 100, "label_x": time_threshold / 2, "label_y": 88, "name": "Klasse II"},
            {"portfolio_class": "III", "x": time_threshold, "x2": 100, "y": 0, "y2": utilization_threshold, "label_x": (time_threshold + 100) / 2, "label_y": 12, "name": "Klasse III"},
            {"portfolio_class": "IV", "x": 0, "x2": time_threshold, "y": 0, "y2": utilization_threshold, "label_x": time_threshold / 2, "label_y": 12, "name": "Klasse IV"},
        ]
    )
    class_scale = alt.Scale(domain=["I", "II", "III", "IV"], range=["#0f766e", "#2563eb", "#0891b2", "#64748b"])
    hover = alt.selection_point(fields=["detection_id"], on="pointerover", nearest=True, empty=False)

    quadrants = (
        alt.Chart(quadrant_df)
        .mark_rect(opacity=0.08)
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100]), title="Geschätzte Nutzungszeit [%]"),
            x2="x2:Q",
            y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 100]), title="Geschätzter Nutzungsgrad [%]"),
            y2="y2:Q",
            color=alt.Color("portfolio_class:N", scale=class_scale, legend=None),
        )
    )
    quadrant_labels = (
        alt.Chart(quadrant_df)
        .mark_text(fontWeight="bold", fontSize=13, opacity=0.72)
        .encode(
            x=alt.X("label_x:Q", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("label_y:Q", scale=alt.Scale(domain=[0, 100])),
            text="name:N",
            color=alt.Color("portfolio_class:N", scale=class_scale, legend=None),
        )
    )
    thresholds = (
        alt.Chart(pd.DataFrame([{"x": time_threshold, "y": utilization_threshold}]))
        .mark_rule(color="#94a3b8", strokeDash=[6, 5], strokeWidth=1.2)
        .encode(x="x:Q")
        + alt.Chart(pd.DataFrame([{"x": time_threshold, "y": utilization_threshold}]))
        .mark_rule(color="#94a3b8", strokeDash=[6, 5], strokeWidth=1.2)
        .encode(y="y:Q")
    )
    points = (
        alt.Chart(df)
        .mark_circle(stroke="#ffffff", strokeWidth=1.4)
        .encode(
            x=alt.X("operating_time_pct:Q", scale=alt.Scale(domain=[0, 100]), title="Geschätzte Nutzungszeit [%]"),
            y=alt.Y("utilization_pct:Q", scale=alt.Scale(domain=[0, 100]), title="Geschätzter Nutzungsgrad [%]"),
            size=alt.Size("bubble_power_kw:Q", title="Nennleistung [kW]", scale=alt.Scale(range=[90, 780])),
            color=alt.Color("portfolio_class:N", title="Klasse", scale=class_scale),
            opacity=alt.condition(hover, alt.value(1), alt.value(0.78)),
            tooltip=[
                alt.Tooltip("detection_id:Q", title="ID"),
                alt.Tooltip("page:Q", title="Seite"),
                alt.Tooltip("identifier:N", title="Kennzeichen"),
                alt.Tooltip("designation:N", title="Bezeichnung"),
                alt.Tooltip("consumer_type:N", title="Typ"),
                alt.Tooltip("tooltip_power:N", title="Nennleistung"),
                alt.Tooltip("tooltip_utilization:N", title="Nutzungsgrad"),
                alt.Tooltip("tooltip_time:N", title="Nutzungszeit"),
                alt.Tooltip("portfolio_class:N", title="Portfolio"),
                alt.Tooltip("metering_recommendation:N", title="Empfehlung"),
            ],
        )
    )
    labels = (
        alt.Chart(df)
        .mark_text(dx=8, dy=-7, fontSize=11, color="#334155")
        .encode(
            x="operating_time_pct:Q",
            y="utilization_pct:Q",
            text="label:N",
            opacity=alt.condition(hover, alt.value(1), alt.value(0.7)),
        )
    )

    chart = (
        alt.layer(quadrants, quadrant_labels, thresholds, points, labels)
        .add_params(hover)
        .properties(height=440)
        .configure_axis(gridColor="#e2e8f0", labelColor="#475569", titleColor="#334155")
        .configure_view(strokeWidth=0)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def render_circuit_tool_app():
    render_workspace_topbar("circuit-tool")
    render_app_sidebar("circuit-tool")

    with st.sidebar:
        st.subheader("Erkennung")
        recognition_mode = st.radio(
            "Modus",
            ["Lokale Textanalyse (keine Tokens)", "KI-Assistenz (OpenAI)"],
            index=0,
            help="Die lokale Textanalyse bleibt auf diesem Rechner. Nur die KI-Assistenz sendet extrahierten PDF-Text an OpenAI.",
        )
        model = None
        if recognition_mode.startswith("KI"):
            model = st.text_input("KI-Modell", value=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        else:
            st.caption("Tokenfrei: Es wird kein OpenAI-API-Aufruf ausgeführt.")
        min_confidence = st.slider("Mindest-Konfidenz", 0.0, 1.0, 0.55, 0.05)

        st.subheader("Priorisierung")
        a_limit = st.slider("ABC-Grenze A [%]", 50, 90, 80, 1)
        b_limit = st.slider("ABC-Grenze B [%]", 80, 98, 90, 1)
        utilization_threshold = st.slider("Portfolio-Grenze Nutzungsgrad [%]", 10, 90, 50, 5)
        time_threshold = st.slider("Portfolio-Grenze Nutzungszeit [%]", 10, 90, 50, 5)

    st.markdown(
        """
        <div class="page-header">
            <div class="eyebrow">KI-Schaltplantool</div>
            <h1>Verbraucher aus elektrischen Schaltplänen priorisieren</h1>
            <p>
                PDF hochladen, Verbraucher und technische Metadaten extrahieren und anschließend
                über ABC-Analyse, Energieportfolio und Tabelle für Messstellenentscheidungen bewerten.
            </p>
        </div>
        <div class="workflow-strip">
            <div class="workflow-step"><b>1. PDF einlesen</b><span>Textbasierte Schaltpläne werden direkt extrahiert; gescannte PDFs melden transparent den OCR-Bedarf.</span></div>
            <div class="workflow-step"><b>2. KI strukturieren</b><span>Die KI-Assistenz erkennt Verbraucher, Nennleistung, Strom, Spannung, Kennzeichen und Seitenbezug.</span></div>
            <div class="workflow-step"><b>3. Priorisieren</b><span>ABC-Analyse und Energieportfolio leiten Messstrategien und Exporttabellen ab.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    upload_col, action_col = st.columns([2, 1])
    with upload_col:
        uploaded_pdf = st.file_uploader("Schaltplan-PDF hochladen", type=["pdf"])
    with action_col:
        st.write("")
        st.write("")
        use_demo = st.button("Demo laden")
        analyze = st.button("PDF analysieren", type="primary")

    if use_demo:
        st.session_state.circuit_result = demo_circuit_result()
        st.session_state.circuit_file_token = "demo"

    if analyze:
        if uploaded_pdf is None:
            st.warning("Bitte zuerst ein PDF hochladen oder die Demo laden.")
        else:
            with st.spinner("Schaltplan wird analysiert..."):
                api_key = get_openai_api_key()
                use_ai = recognition_mode.startswith("KI")
                result = analyze_circuit_pdf(
                    uploaded_pdf.getvalue(),
                    uploaded_pdf.name,
                    use_ai=use_ai,
                    api_key=api_key,
                    model=model,
                )
                st.session_state.circuit_result = result
                st.session_state.circuit_file_token = f"{uploaded_pdf.name}-{uploaded_pdf.size}"

    result = st.session_state.get("circuit_result")
    if result and result.get("extraction_version") not in {LOCAL_EXTRACTION_VERSION, "Demo"}:
        st.session_state.pop("circuit_result", None)
        result = None
        st.info("Die lokale Erkennung wurde aktualisiert. Bitte das PDF erneut analysieren.")
    if not result:
        st.info(
            "Noch kein Schaltplan analysiert. Lade die Demo oder analysiere ein PDF; danach erscheinen darunter die Ansichten "
            "Tabelle, ABC-Analyse, Energieportfolio und Export."
        )
        return

    for message in result.get("messages", []):
        st.warning(message)

    st.caption(
        f"Erkennung: {result.get('recognition_engine', 'unbekannt')} · "
        f"Textextraktion: {result.get('text_engine', 'unbekannt')} · "
        f"Version: {result.get('extraction_version', 'alt')}"
    )

    raw_df = consumers_to_dataframe(result.get("consumers", []))
    if not raw_df.empty:
        raw_df = raw_df[pd.to_numeric(raw_df["confidence"], errors="coerce").fillna(0) >= min_confidence]

    known_power = pd.to_numeric(raw_df.get("nominal_power_kw", pd.Series(dtype=float)), errors="coerce").fillna(0)
    if raw_df.empty:
        st.error(
            "Es wurden keine Verbraucher mit der aktuellen Konfidenzgrenze gefunden. "
            "Senke links in der Sidebar die Mindest-Konfidenz oder lade die Demo, damit ABC-Analyse und Energieportfolio sichtbar werden."
        )
        return

    abc_summary_df = build_abc_analysis(raw_df, a_limit=a_limit, b_limit=b_limit)
    portfolio_summary_df = classify_portfolio(
        prepare_portfolio_input(raw_df),
        utilization_threshold=utilization_threshold,
        time_threshold=time_threshold,
    )
    high_abc_count = (
        int(abc_summary_df["abc_group"].isin(["A", "B"]).sum()) if not abc_summary_df.empty else 0
    )
    class_i_count = (
        int((portfolio_summary_df["portfolio_class"] == "I").sum()) if not portfolio_summary_df.empty else 0
    )
    top_consumer = "Keine Nennleistung"
    if known_power.sum() > 0:
        top_index = known_power.idxmax()
        top_consumer = str(raw_df.loc[top_index, "designation"])[:34]

    st.markdown(
        f"""
        <div class="result-summary">
            <div class="summary-card">
                <span>Erkannte Verbraucher</span>
                <b>{len(raw_df)}</b>
                <em>{escape(str(result.get("recognition_engine", "-")))}</em>
            </div>
            <div class="summary-card">
                <span>Summe Nennleistung</span>
                <b>{known_power.sum():.2f} kW</b>
                <em>{escape(top_consumer)}</em>
            </div>
            <div class="summary-card">
                <span>ABC-Fokus</span>
                <b>{high_abc_count}</b>
                <em>A/B-Verbraucher priorisiert</em>
            </div>
            <div class="summary-card">
                <span>Portfolio-Klasse I</span>
                <b>{class_i_count}</b>
                <em>für kontinuierliche Messung</em>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="insight-strip">
            <div class="insight-tile"><b>Automatisierte Extraktion</b><span>PDF-Text oder KI-Modell liefern eine strukturierte Verbraucherliste mit Seitenbezug und Konfidenz.</span></div>
            <div class="insight-tile"><b>Messpriorität</b><span>Die ABC-Analyse verdichtet Nennleistungen zu einer klaren Reihenfolge für den Start der Messkampagne.</span></div>
            <div class="insight-tile"><b>Portfolio-Entscheidung</b><span>Nutzungsgrad und Nutzungszeit ergänzen die Nennleistung zu einer belastbareren Monitoring-Strategie.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Auswertung")
    st.caption(
        "Die ABC-Analyse und das Energieportfolio sind eigene Ansichten in dieser Tab-Leiste. "
        "Beim Energieportfolio können Nutzungsgrad und Nutzungszeit direkt in der Tabelle angepasst werden."
    )
    table_tab, abc_tab, portfolio_tab, export_tab = st.tabs(
        ["Tabelle der Verbraucher", "ABC-Analyse", "Energieportfolio", "Export"]
    )

    with table_tab:
        display_df = raw_df[
            [
                "detection_id",
                "page",
                "identifier",
                "designation",
                "consumer_type",
                "nominal_power_kw",
                "nominal_current_a",
                "voltage_v",
                "cabinet",
                "confidence",
                "source",
            ]
        ].rename(
            columns={
                "detection_id": "ID",
                "page": "Seite",
                "identifier": "Kennzeichen",
                "designation": "Bezeichnung",
                "consumer_type": "Typ",
                "nominal_power_kw": "Nennleistung [kW]",
                "nominal_current_a": "Nennstrom [A]",
                "voltage_v": "Spannung [V]",
                "cabinet": "Schaltschrank",
                "confidence": "Konfidenz",
                "source": "Quelle",
            }
        )
        st.dataframe(display_df, width="stretch", hide_index=True)
        with st.expander("Erkennungsbelege anzeigen"):
            st.dataframe(
                raw_df[["detection_id", "page", "designation", "source_snippet"]],
                width="stretch",
                hide_index=True,
            )

    with abc_tab:
        abc_df = build_abc_analysis(raw_df, a_limit=a_limit, b_limit=b_limit)
        render_abc_chart(abc_df, a_limit, b_limit)
        if not abc_df.empty:
            st.dataframe(
                abc_df[
                    [
                        "detection_id",
                        "identifier",
                        "designation",
                        "nominal_power_kw",
                        "share_power_pct",
                        "cum_power_pct",
                        "cum_consumers_pct",
                        "abc_group",
                    ]
                ].rename(
                    columns={
                        "detection_id": "ID",
                        "identifier": "Kennzeichen",
                        "designation": "Bezeichnung",
                        "nominal_power_kw": "Nennleistung [kW]",
                        "share_power_pct": "Anteil Leistung [%]",
                        "cum_power_pct": "Kumulierte Leistung [%]",
                        "cum_consumers_pct": "Kumulierte Verbraucher [%]",
                        "abc_group": "ABC",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

    with portfolio_tab:
        editable = prepare_portfolio_input(raw_df)
        edited_df = st.data_editor(
            editable[
                [
                    "detection_id",
                    "identifier",
                    "designation",
                    "consumer_type",
                    "nominal_power_kw",
                    "utilization_pct",
                    "operating_time_pct",
                ]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "detection_id": st.column_config.NumberColumn("ID", disabled=True),
                "identifier": st.column_config.TextColumn("Kennzeichen", disabled=True),
                "designation": st.column_config.TextColumn("Bezeichnung", disabled=True),
                "consumer_type": st.column_config.TextColumn("Typ", disabled=True),
                "nominal_power_kw": st.column_config.NumberColumn("Nennleistung [kW]", disabled=True, format="%.2f"),
                "utilization_pct": st.column_config.NumberColumn("Nutzungsgrad [%]", min_value=0, max_value=100, step=5),
                "operating_time_pct": st.column_config.NumberColumn("Nutzungszeit [%]", min_value=0, max_value=100, step=5),
            },
            key=f"portfolio_editor_{st.session_state.get('circuit_file_token', 'current')}",
        )
        portfolio_df = classify_portfolio(
            edited_df,
            utilization_threshold=utilization_threshold,
            time_threshold=time_threshold,
        )
        render_portfolio_plot(portfolio_df, utilization_threshold, time_threshold)
        st.dataframe(
            portfolio_df[
                [
                    "detection_id",
                    "identifier",
                    "designation",
                    "portfolio_class",
                    "metering_recommendation",
                ]
            ].rename(
                columns={
                    "detection_id": "ID",
                    "identifier": "Kennzeichen",
                    "designation": "Bezeichnung",
                    "portfolio_class": "Portfolio-Klasse",
                    "metering_recommendation": "Messstrategie",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    with export_tab:
        export_df = raw_df.copy()
        abc_export = build_abc_analysis(export_df, a_limit=a_limit, b_limit=b_limit)
        if not abc_export.empty:
            export_df = export_df.merge(
                abc_export[["detection_id", "abc_group", "share_power_pct", "cum_power_pct"]],
                on="detection_id",
                how="left",
            )
        st.download_button(
            "Verbrauchertabelle als CSV exportieren",
            data=export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="schaltplan_verbraucher.csv",
            mime="text/csv",
        )
        st.caption(
            "Hinweis: Die KI-Assistenz ersetzt keine technische Prüfung. Erkannte Verbraucher und Nennwerte sollten am Originalschaltplan validiert werden."
        )


def render_header():
    st.markdown(
        """
        <div class="hero">
            <h1>⚡ Energieeffizienz-Check für Fertigungsunternehmen</h1>
            <p>
                Identifizieren Sie Energieeffizienzpotenziale anhand produktionsnaher Daten,
                Lastgang-Analyse, Zyklenerkennung und automatisch generierter Kennzahlen.
            </p>
            <div class="badge-row">
                <span class="badge">Produktionsdaten</span>
                <span class="badge">Grundlastanalyse</span>
                <span class="badge">Lastspitzen</span>
                <span class="badge">Zyklenerkennung</span>
                <span class="badge">PDF-Bericht</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_progress():
    labels = ["Unternehmen", "Produktion", "Energie", "Prozesse", "Lastgang", "Bericht"]
    step = st.session_state.step
    st.progress(step / len(labels))
    st.caption(" → ".join([f"**{label}**" if i + 1 == step else label for i, label in enumerate(labels)]))


def nav_buttons(show_next=True, next_label="Weiter"):
    left, right = st.columns([1, 1])
    with left:
        if st.session_state.step > 1:
            st.button("← Zurück", on_click=previous_step)
    with right:
        if show_next:
            st.button(next_label, on_click=next_step)


def render_recommendation_card(rec):
    css_class = {
        "hoch": "recommendation-high",
        "mittel": "recommendation-medium",
        "niedrig": "recommendation-low",
    }.get(rec["priority"], "recommendation-low")

    st.markdown(
        f"""
        <div class="insight {css_class}">
            <b>{rec['priority'].upper()} · {rec['title']}</b><br>
            <span class="small-muted">{rec['reason']}</span><br>
            {rec['impact']}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    with st.sidebar:
        st.header("Demo-Modus")
        st.write("Diese App ist ein Dummy-Prototyp für eine mögliche Energieeffizienzplattform.")
        st.info("Ohne Upload wird ein synthetischer Lastgang erzeugt, damit die Analyse direkt getestet werden kann.")
        st.subheader("Nächste Produktidee")
        st.caption("Später könnten Nutzer Projekte speichern, Teams einladen und mehrere Standorte vergleichen.")
        if st.button("Demo zurücksetzen"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def step_company():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("1. Unternehmenskontext")
    st.write("Bitte geben Sie einige Rahmendaten zum Standort ein.")

    c1, c2 = st.columns(2)
    with c1:
        company_name = st.text_input("Unternehmensname", value=st.session_state.company_data.get("company_name", "Musterfertigung GmbH"))
        industry = st.selectbox(
            "Branche",
            ["Metallverarbeitung", "Kunststoffverarbeitung", "Lebensmittel", "Automotive", "Chemie", "Elektronik", "Sonstige"],
            index=0,
        )
    with c2:
        location = st.text_input("Standort", value=st.session_state.company_data.get("location", "Deutschland"))
        employees = st.number_input("Mitarbeitende am Standort", min_value=1, value=int(st.session_state.company_data.get("employees", 120)))

    st.session_state.company_data = {
        "company_name": company_name,
        "industry": industry,
        "location": location,
        "employees": employees,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


def step_production():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("2. Produktionsdaten")
    st.write("Diese Angaben helfen, Energieverbrauch mit Produktionsleistung und Betriebszeiten zu verknüpfen.")

    c1, c2 = st.columns(2)
    with c1:
        shift_model = st.selectbox("Schichtmodell", ["1-Schicht", "2-Schicht", "3-Schicht", "Kontinuierlich / 24-7"], index=1)
        operating_days = st.slider("Produktionstage pro Woche", min_value=1, max_value=7, value=5)
        annual_output = st.number_input("Jährliche Produktionsmenge [Stück/Jahr]", min_value=1, value=100000)
    with c2:
        main_product = st.text_input("Hauptprodukt / Produktgruppe", value="Bauteil A")
        scrap_rate = st.slider("Ausschussquote [%]", min_value=0.0, max_value=25.0, value=3.5, step=0.5)
        bottleneck = st.text_input("Engpassprozess", value="CNC-Bearbeitung")

    st.session_state.production_data = {
        "shift_model": shift_model,
        "operating_days": operating_days,
        "annual_output": annual_output,
        "main_product": main_product,
        "scrap_rate": scrap_rate,
        "bottleneck": bottleneck,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


def step_energy():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("3. Energiebezogene Daten")
    st.write("Hier werden zentrale Energiedaten erfasst, um Potenziale monetär und energetisch grob zu bewerten.")

    c1, c2 = st.columns(2)
    with c1:
        annual_electricity = st.number_input("Jährlicher Stromverbrauch [kWh/Jahr]", min_value=0, value=850000)
        electricity_price = st.number_input("Strompreis [EUR/kWh]", min_value=0.0, value=0.22, step=0.01)
        peak_price = st.number_input("Leistungspreis [EUR/kW/Jahr]", min_value=0.0, value=120.0, step=5.0)
    with c2:
        has_iso = st.selectbox("Energiemanagement vorhanden?", ["Nein", "ISO 50001", "Energieaudit", "Internes Monitoring"], index=3)
        metering_level = st.selectbox("Messkonzept", ["Nur Hauptzähler", "Linienzähler", "Maschinenzähler", "Energiemonitoring-System"], index=1)
        other_media = st.multiselect("Weitere Medien", ["Druckluft", "Erdgas", "Wärme", "Kälte", "Dampf", "Wasser"], default=["Druckluft"])

    st.session_state.energy_data = {
        "annual_electricity": annual_electricity,
        "electricity_price": electricity_price,
        "peak_price": peak_price,
        "has_iso": has_iso,
        "metering_level": metering_level,
        "other_media": other_media,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


def step_processes():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("4. Prozesse und vermutete Potenziale")
    st.write("Wählen Sie Prozessbereiche, in denen Sie Einsparpotenziale vermuten.")

    c1, c2 = st.columns(2)
    with c1:
        process_areas = st.multiselect(
            "Relevante Prozessbereiche",
            ["Druckluft", "Absaugung", "Pumpen", "Antriebe", "Kälte", "Wärme", "Beleuchtung", "Standby-Verbrauch", "Gebäudeleittechnik"],
            default=["Druckluft", "Antriebe", "Standby-Verbrauch"],
        )
        maintenance = st.selectbox("Wartungsstrategie", ["Reaktiv", "Regelmäßig", "Zustandsorientiert", "Predictive Maintenance"], index=1)
    with c2:
        known_issues = st.text_area(
            "Bekannte Auffälligkeiten",
            value="Erhöhte Grundlast am Wochenende; einzelne Lastspitzen beim parallelen Anfahren mehrerer Anlagen.",
            height=120,
        )
        goals = st.multiselect(
            "Zielsetzung",
            ["Energiekosten senken", "CO2 reduzieren", "Lastspitzen vermeiden", "Transparenz schaffen", "Audit vorbereiten"],
            default=["Energiekosten senken", "Lastspitzen vermeiden", "Transparenz schaffen"],
        )

    st.session_state.process_data = {
        "process_areas": process_areas,
        "maintenance": maintenance,
        "known_issues": known_issues,
        "goals": goals,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


def step_load_profile():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5. Lastgang hochladen und analysieren")
    st.write("Laden Sie eine CSV- oder Excel-Datei mit Zeitstempel und Leistung hoch. Für die Demo können Sie den Upload überspringen.")

    uploaded = st.file_uploader("Lastgang-Datei hochladen", type=["csv", "xlsx"])
    st.caption("Erwartete Spalten zum Beispiel: `timestamp`, `power_kw`. Andere Spaltennamen werden heuristisch erkannt.")

    if st.button("Analyse starten"):
        try:
            df = read_load_profile(uploaded)
            analysis = analyze_load_profile(df, st.session_state.production_data, st.session_state.energy_data)
            st.session_state.df = df
            st.session_state.analysis = analysis
            st.success("Analyse abgeschlossen. Ergebnisse wurden berechnet.")
        except Exception as exc:
            st.error(f"Die Datei konnte nicht verarbeitet werden: {exc}")

    if st.session_state.analysis is not None:
        analysis = st.session_state.analysis
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Energie", f"{analysis['total_energy']:,.0f} kWh")
        m2.metric("Peak", f"{analysis['peak_power']:,.1f} kW")
        m3.metric("Grundlast", f"{analysis['base_load']:,.1f} kW")
        m4.metric("Nicht-Produktion", f"{analysis['non_production_share'] * 100:.1f} %")
        m5.metric("Zyklen", f"{analysis['detected_cycles']}")

        tab1, tab2, tab3, tab4 = st.tabs(["Lastgang", "Tagesenergie", "Heatmap", "Lastspitzen"])
        with tab1:
            chart_df = analysis["df"].set_index("timestamp")[["power_kw"]]
            st.line_chart(chart_df)
            st.caption("Die Zyklenerkennung basiert in dieser Demo auf einem gleitenden Mittelwert und einem Quantil-Schwellenwert.")
        with tab2:
            daily = analysis["daily_energy"].copy()
            daily["date"] = pd.to_datetime(daily["date"])
            st.bar_chart(daily.set_index("date")[["energy_kwh"]])
        with tab3:
            st.dataframe(analysis["heatmap_data"].style.format("{:.0f}"), width="stretch")
            st.caption("Durchschnittliche Leistung je Wochentag und Stunde. Hohe Werte außerhalb geplanter Produktion deuten auf Grundlastpotenziale hin.")
        with tab4:
            st.dataframe(analysis["top_peaks"], width="stretch")
            st.caption("Diese Zeitpunkte sind Kandidaten für Lastspitzenmanagement oder detaillierte Ursachenanalyse.")

        st.info("Enthalten: Heatmap, Peak-Liste, Nicht-Produktionsanteil, annualisierte Energie, CO2-Potenzial und priorisierte Empfehlungen.")

    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons(show_next=st.session_state.analysis is not None, next_label="Zum Bericht")


def step_report():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("6. Ergebnisbericht erhalten")

    if st.session_state.analysis is None:
        st.warning("Bitte führen Sie zuerst eine Lastgang-Analyse aus.")
        nav_buttons(show_next=False)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    analysis = st.session_state.analysis

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Einsparpotenzial", f"{analysis['estimated_savings_kwh']:,.0f} kWh")
    c2.metric("Potenzial monetär", f"{analysis['estimated_savings_eur']:,.0f} EUR")
    c3.metric("CO2-Potenzial", f"{analysis['estimated_co2_savings_t']:.1f} t")
    c4.metric("Peak-Potenzial/Jahr", f"{analysis['peak_savings_eur_year']:,.0f} EUR")

    st.subheader("Priorisierte Handlungsempfehlungen")
    for rec in analysis["recommendations"]:
        render_recommendation_card(rec)

    with st.expander("Technische Kennzahlen anzeigen"):
        kpi_table = pd.DataFrame(
            {
                "Kennzahl": [
                    "Analysierte Tage",
                    "Gesamtenergie [kWh]",
                    "Annualisierte Energie [kWh/Jahr]",
                    "Maximale Leistung [kW]",
                    "Durchschnittsleistung [kW]",
                    "Grundlast [kW]",
                    "Lastfaktor",
                    "Nicht-Produktionsanteil [%]",
                    "Zyklusenergieanteil [%]",
                    "Energie je Einheit [kWh/Stück]",
                ],
                "Wert": [
                    analysis["analyzed_days"],
                    round(analysis["total_energy"], 0),
                    round(analysis["annualized_energy"], 0),
                    round(analysis["peak_power"], 1),
                    round(analysis["avg_power"], 1),
                    round(analysis["base_load"], 1),
                    round(analysis["load_factor"], 2),
                    round(analysis["non_production_share"] * 100, 1),
                    round(analysis["cycle_energy_share"] * 100, 1),
                    round(analysis["energy_per_unit"], 3),
                ],
            }
        )
        st.dataframe(kpi_table, width="stretch")

    st.divider()
    st.write("Bitte geben Sie eine E-Mail-Adresse ein. Der PDF-Bericht wird ausschließlich per E-Mail als Anhang versendet.")
    email = st.text_input("E-Mail-Adresse", value=st.session_state.email, placeholder="name@unternehmen.de")
    st.session_state.email = email

    if email and not is_valid_email(email):
        st.error("Bitte geben Sie eine gültige E-Mail-Adresse ein.")
    elif is_valid_email(email):
        if st.button("Bericht per E-Mail senden"):
            try:
                pdf_bytes = create_pdf_report(
                    st.session_state.company_data,
                    st.session_state.production_data,
                    st.session_state.energy_data,
                    st.session_state.process_data,
                    analysis,
                )
                send_pdf_report_email(
                    recipient_email=email,
                    pdf_bytes=pdf_bytes,
                    company_name=st.session_state.company_data.get("company_name", ""),
                )
                st.success("Der PDF-Bericht wurde per E-Mail versendet.")
            except Exception as exc:
                st.error(f"Die E-Mail konnte nicht versendet werden: {exc}")
    else:
        st.warning("Der Bericht wird erst nach Eingabe einer gültigen E-Mail-Adresse versendet.")

    nav_buttons(show_next=False)
    st.markdown('</div>', unsafe_allow_html=True)


def render_load_analysis_app():
    init_state()
    render_workspace_topbar("load-analysis")
    render_header()
    render_progress()
    render_app_sidebar("load-analysis")
    render_sidebar()

    if st.session_state.step == 1:
        step_company()
    elif st.session_state.step == 2:
        step_production()
    elif st.session_state.step == 3:
        step_energy()
    elif st.session_state.step == 4:
        step_processes()
    elif st.session_state.step == 5:
        step_load_profile()
    elif st.session_state.step == 6:
        step_report()


def main():
    active_app = get_active_app()

    if active_app == "load-analysis":
        render_load_analysis_app()
    elif active_app == "measures-catalog":
        render_measures_catalog_app()
    elif active_app == "circuit-tool":
        render_circuit_tool_app()
    else:
        render_landing_page()


if __name__ == "__main__":
    main()
