"""
Gravel Coach v5 — Dashboard 5 pages, design fidèle au mockup Lovable.

Navigation par sidebar (5 pages) :
  1. Tableau de bord
  2. Activités
  3. Performance
  4. Coach IA
  5. Objectifs

Lancer en local :
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import datetime as dt
import json
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import db
from analysis import (
    DEFAULT_ZONES,
    best_efforts,
    intensity_factor,
    normalized_power,
    performance_management_chart,
    training_stress_score,
    z2_progress,
    zone_bounds_watts,
)
from coach import generate_coach_report
from file_import import parse_file, extract_summary_from_df
from ride_detail import render_ride_analysis
from sync import sync_recent, sync_strava
from garmin_sync import login_step1, login_step2_mfa
import strava_sync

st.set_page_config(page_title="Gravel Coach", page_icon="🚵", layout="wide")

# ───────────────────────── Strava OAuth callback ─────────────────────────
_strava_code = st.query_params.get("code")
_strava_scope = st.query_params.get("scope", "")
if _strava_code and "activity:read" in _strava_scope:
    try:
        tokens = strava_sync.exchange_code(_strava_code)
        st.session_state["strava_just_connected"] = True
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Échec de la connexion Strava : {e}")
        st.query_params.clear()

# ════════════════════════════════════════════════════════════════════════════
#  COLOR PALETTE  &  DESIGN TOKENS
# ════════════════════════════════════════════════════════════════════════════
C = {
    "bg":        "#2b2520",
    "card":      "#38322d",
    "sidebar":   "#221e1a",
    "muted":     "#3f3832",
    "border":    "#4d453e",
    "text":      "#f0ece8",
    "text2":     "#b5ada5",
    "text_m":    "#8a8279",
    "primary":   "#c4873a",
    "primary_fg":"#1a1612",
    "accent":    "#6db56d",
    "chart1":    "#c4873a",
    "chart2":    "#6db56d",
    "chart3":    "#d4b74a",
    "chart4":    "#5ba0c4",
    "chart5":    "#c45a5a",
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Hind, sans-serif", color=C["text2"], size=12),
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis=dict(gridcolor="rgba(77,69,62,0.4)", zerolinecolor="rgba(77,69,62,0.4)"),
    yaxis=dict(gridcolor="rgba(77,69,62,0.4)", zerolinecolor="rgba(77,69,62,0.4)"),
    legend=dict(font=dict(size=11, color=C["text2"])),
    hoverlabel=dict(bgcolor=C["card"], font_size=12, font_family="Hind"),
)

# ════════════════════════════════════════════════════════════════════════════
#  CSS — Dark Gravel Coach Theme
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=Hind:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-dark:        #2b2520;
    --bg-card:        #38322d;
    --bg-sidebar:     #221e1a;
    --bg-muted:       #3f3832;
    --border:         #4d453e;
    --text-primary:   #f0ece8;
    --text-secondary: #b5ada5;
    --text-muted:     #8a8279;
    --primary:        #c4873a;
    --primary-fg:     #1a1612;
    --accent:         #6db56d;
    --chart-1:        #c4873a;
    --chart-2:        #6db56d;
    --chart-3:        #d4b74a;
    --chart-4:        #5ba0c4;
    --chart-5:        #c45a5a;
    --ember-start:    #c4873a;
    --ember-end:      #d4b74a;
    --radius:         0.75rem;
}

/* ── Fonts ── */
html, body, [class*="st-"] {
    font-family: 'Hind', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
h1, h2, h3, h4, .font-display {
    font-family: 'Archivo', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.mono { font-family: 'JetBrains Mono', monospace !important; }

/* ── Global dark ── */
.stApp, .main .block-container {
    background: var(--bg-dark) !important;
    color: var(--text-primary) !important;
}
.stApp { background-color: var(--bg-dark) !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
    width: 240px !important;
}
section[data-testid="stSidebar"] > div {
    background: var(--bg-sidebar) !important;
}
section[data-testid="stSidebar"] .stRadio label {
    color: var(--text-secondary) !important;
    padding: 8px 16px !important;
    border-radius: 8px !important;
    margin-bottom: 2px !important;
    transition: all 0.15s;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(196,135,58,0.08) !important;
    color: var(--text-primary) !important;
}
section[data-testid="stSidebar"] .stRadio [data-checked="true"] + label,
section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background: rgba(196,135,58,0.12) !important;
    color: var(--primary) !important;
    font-weight: 600 !important;
}
/* Hide radio circles */
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] > div > div:first-child {
    display: none !important;
}

/* ── Cards (Section containers) ── */
.gc-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 16px;
}
.gc-card-muted {
    background: var(--bg-muted);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
}

/* ── Page Title (kicker + heading) ── */
.gc-kicker {
    font-family: 'Archivo', sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--primary);
    margin-bottom: 4px;
}
.gc-page-title {
    font-family: 'Archivo', sans-serif;
    font-size: 1.85rem;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.15;
    margin: 0 0 24px 0;
}

/* ── Stat component ── */
.gc-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.gc-stat-label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--text-muted);
}
.gc-stat-row {
    display: flex;
    align-items: baseline;
    gap: 6px;
}
.gc-stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.6rem;
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1.2;
}
.gc-stat-unit {
    font-size: 0.75rem;
    color: var(--text-muted);
}
.gc-stat-delta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 500;
}
.gc-delta-up { color: var(--accent); }
.gc-delta-down { color: var(--chart-5); }
.gc-delta-neutral { color: var(--text-muted); }

/* ── Coach reco card (with topo pattern) ── */
.gc-coach-reco {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}
.gc-coach-reco::before {
    content: "";
    position: absolute;
    inset: 0;
    opacity: 0.04;
    background: repeating-radial-gradient(circle at 20% 50%, transparent 0, rgba(196,135,58,0.12) 40px),
                repeating-radial-gradient(circle at 80% 50%, transparent 0, rgba(196,135,58,0.08) 40px);
    pointer-events: none;
}
.gc-coach-reco-title {
    font-family: 'Archivo', sans-serif;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--primary);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.gc-coach-reco-text {
    color: var(--text-secondary);
    font-size: 0.9rem;
    line-height: 1.5;
    position: relative;
}

/* ── Section title ── */
.gc-section-title {
    font-family: 'Archivo', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 16px;
}

/* ── Activity row cards ── */
.gc-activity-row {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: border-color 0.15s;
}
.gc-activity-row:hover {
    border-color: var(--primary);
}
.gc-activity-title {
    font-family: 'Archivo', sans-serif;
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-primary);
}
.gc-activity-meta {
    font-size: 0.75rem;
    color: var(--text-muted);
}
.gc-activity-stats {
    display: flex;
    gap: 24px;
    align-items: center;
}
.gc-activity-stat-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    color: var(--text-primary);
}
.gc-activity-stat-lbl {
    font-size: 0.6rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* ── Filter pills ── */
.gc-pills {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
.gc-pill {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    background: transparent;
    transition: all 0.15s;
}
.gc-pill:hover { border-color: var(--primary); color: var(--text-primary); }
.gc-pill-active {
    background: var(--primary) !important;
    color: var(--primary-fg) !important;
    border-color: var(--primary) !important;
    font-weight: 600;
}

/* ── Progress bar (ember gradient) ── */
.gc-progress-track {
    width: 100%;
    height: 8px;
    background: var(--bg-muted);
    border-radius: 999px;
    overflow: hidden;
}
.gc-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--ember-start), var(--ember-end));
    transition: width 0.3s ease;
}

/* ── Zone bars ── */
.gc-zone-bar-track {
    width: 100%;
    height: 20px;
    background: var(--bg-muted);
    border-radius: 6px;
    overflow: hidden;
}
.gc-zone-bar-fill {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(135deg, var(--ember-start), var(--ember-end));
}

/* ── Chat bubbles ── */
.gc-chat-me {
    background: var(--primary);
    color: var(--primary-fg);
    border-radius: 12px 12px 4px 12px;
    padding: 12px 16px;
    margin: 8px 0;
    max-width: 80%;
    margin-left: auto;
    font-size: 0.9rem;
}
.gc-chat-ai {
    background: var(--bg-muted);
    color: var(--text-primary);
    border-radius: 12px 12px 12px 4px;
    padding: 12px 16px;
    margin: 8px 0;
    max-width: 80%;
    font-size: 0.9rem;
    line-height: 1.55;
}

/* ── Suggestion chips ── */
.gc-chip {
    display: inline-block;
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin: 4px;
    cursor: pointer;
    transition: all 0.15s;
}
.gc-chip:hover { border-color: var(--primary); color: var(--primary); }

/* ── Goal card ── */
.gc-goal-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    position: relative;
    overflow: hidden;
}
.gc-goal-card-featured {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    position: relative;
    overflow: hidden;
}
.gc-goal-card-featured::before {
    content: "";
    position: absolute;
    inset: 0;
    opacity: 0.04;
    background: repeating-radial-gradient(circle at 20% 50%, transparent 0, rgba(196,135,58,0.12) 40px),
                repeating-radial-gradient(circle at 80% 50%, transparent 0, rgba(196,135,58,0.08) 40px);
    pointer-events: none;
}

/* ── Streamlit overrides ── */
.stTabs [data-baseweb="tab-list"] { display: none !important; }
.stMarkdown a { color: var(--primary) !important; }
div[data-testid="stExpander"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}
div[data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
}
.stButton > button {
    background: var(--primary) !important;
    color: var(--primary-fg) !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Archivo', sans-serif !important;
    font-weight: 600 !important;
    padding: 8px 20px !important;
}
.stButton > button:hover {
    filter: brightness(1.1);
}
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    background: var(--bg-muted) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
.stSelectbox > div > div {
    background: var(--bg-muted) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

/* ── Last ride detail grid ── */
.gc-ride-detail-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}
.gc-ride-detail-item {
    background: var(--bg-muted);
    border-radius: 8px;
    padding: 12px 16px;
}

/* ── Records grid (performance page) ── */
.gc-records-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}
.gc-record-item {
    background: var(--bg-muted);
    border-radius: 8px;
    padding: 14px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.gc-record-label {
    font-size: 0.8rem;
    color: var(--text-muted);
}
.gc-record-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    color: var(--text-primary);
}
.gc-record-delta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--accent);
}

/* ── Weekly program (coach) ── */
.gc-week-day {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid rgba(77,69,62,0.3);
}
.gc-week-day:last-child { border-bottom: none; }
.gc-week-day-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
    min-width: 30px;
}
.gc-week-day-desc {
    font-size: 0.85rem;
    color: var(--text-secondary);
}
.gc-week-day-rest {
    font-size: 0.85rem;
    color: var(--text-muted);
    font-style: italic;
}

/* ── Prep checklist (objectives) ── */
.gc-checklist-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: var(--bg-muted);
    border-radius: 8px;
    margin-bottom: 6px;
}
.gc-check-icon {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
}
.gc-check-done {
    background: var(--accent);
    color: white;
}
.gc-check-pending {
    background: var(--bg-card);
    border: 2px solid var(--border);
}

/* ── Import button (dashed) ── */
.gc-import-btn {
    border: 2px dashed var(--border);
    border-radius: var(--radius);
    padding: 14px 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.15s;
}
.gc-import-btn:hover {
    border-color: var(--primary);
    color: var(--primary);
}

/* ── Comparison rows (activity detail) ── */
.gc-comparison-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: var(--bg-muted);
    border-radius: 8px;
    margin-bottom: 6px;
}
.gc-comparison-label {
    font-size: 0.8rem;
    color: var(--text-muted);
}
.gc-comparison-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9rem;
    color: var(--accent);
}

/* ── New goal button ── */
.gc-new-goal {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.15s;
}
.gc-new-goal:hover {
    border-color: var(--primary);
}
.gc-new-goal-icon {
    font-size: 1.4rem;
    margin-bottom: 4px;
}
.gc-new-goal-text {
    font-size: 0.8rem;
    color: var(--text-secondary);
}

/* Divider */
.gc-divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 20px 0;
}

/* Hide Streamlit chrome */
#MainMenu { display: none; }
header[data-testid="stHeader"] { display: none; }
footer { display: none; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def fmt_duration(seconds: float | None) -> str:
    """Format seconds → 'Xh XXmin'."""
    if seconds is None or math.isnan(seconds):
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m:02d}min"
    return f"{m}min"


def fmt_km(meters: float | None) -> str:
    if meters is None or math.isnan(meters):
        return "—"
    return f"{meters / 1000:.1f}"


def fmt_val(v, decimals=0, fallback="—"):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return fallback
    if decimals == 0:
        return f"{int(round(v))}"
    return f"{v:.{decimals}f}"


def delta_html(value, suffix="", reverse=False):
    """Return colored delta HTML."""
    if value is None:
        return ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(value):
        return ""
    sign = "+" if value >= 0 else ""
    # Format nicely: integer if whole, else 2 decimals
    v_str = f"{value:.0f}" if value == int(value) else f"{value:.2f}"
    cls = "gc-delta-up" if (value >= 0) != reverse else "gc-delta-down"
    return f'<span class="gc-stat-delta {cls}">{sign}{v_str}{suffix}</span>'


def stat_html(label: str, value: str, unit: str = "", delta=None, delta_suffix=""):
    """Render a Stat component matching Lovable design."""
    d = ""
    if delta is not None:
        d = delta_html(delta, delta_suffix)
    return f"""
    <div class="gc-stat">
        <div class="gc-stat-label">{label}</div>
        <div class="gc-stat-row">
            <span class="gc-stat-value">{value}</span>
            <span class="gc-stat-unit">{unit}</span>
            {d}
        </div>
    </div>"""


def section_start(title: str, action_html: str = ""):
    """Open a card section with a title."""
    act = f'<div style="margin-left:auto">{action_html}</div>' if action_html else ""
    return f"""<div class="gc-card">
        <div style="display:flex;align-items:center;margin-bottom:16px">
            <div class="gc-section-title" style="margin-bottom:0">{title}</div>
            {act}
        </div>"""


def section_end():
    return "</div>"


def make_plotly_fig(**extra) -> go.Figure:
    """Create a Plotly figure pre-configured with the dark theme."""
    fig = go.Figure()
    layout = {**PLOTLY_LAYOUT, **extra}
    fig.update_layout(**layout)
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def load_data():
    df = db.load_activities_df()
    return df


def get_rider_profile():
    """Load rider profile from session or defaults."""
    return {
        "name": st.session_state.get("rider_name", "Paul"),
        "weight": st.session_state.get("weight", 72.0),
        "ftp": st.session_state.get("ftp", 268),
        "hr_rest": st.session_state.get("hr_rest", 48),
        "hr_max": st.session_state.get("hr_max", 186),
        "vo2max": st.session_state.get("vo2max", 54),
    }


# ════════════════════════════════════════════════════════════════════════════
#  SIDEBAR — Logo + Navigation + Settings
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    # ── Logo ──
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;padding:8px 0 20px 0">
        <div style="width:36px;height:36px;border-radius:10px;
                    background:linear-gradient(135deg,#c4873a,#d4b74a);
                    display:flex;align-items:center;justify-content:center;
                    font-family:'Archivo',sans-serif;font-weight:800;
                    font-size:1.1rem;color:#1a1612">G</div>
        <div>
            <div style="font-family:'Archivo',sans-serif;font-weight:700;
                        font-size:0.95rem;color:#f0ece8;line-height:1.2">Gravel Coach</div>
            <div style="font-size:0.65rem;color:#8a8279">Analyse & Coaching</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Navigation ──
    NAV_ITEMS = ["🏠  Tableau de bord", "🚴  Activités", "📊  Performance", "💬  Coach IA", "⛰️  Objectifs"]
    page = st.radio("Navigation", NAV_ITEMS, label_visibility="collapsed")

    st.markdown("<hr style='border:none;border-top:1px solid #4d453e;margin:16px 0'>", unsafe_allow_html=True)

    # ── Settings expander ──
    with st.expander("⚙️ Profil & Sync", expanded=False):
        rider = get_rider_profile()
        new_ftp = st.number_input("FTP (W)", value=rider["ftp"], min_value=50, max_value=500, step=1)
        new_weight = st.number_input("Poids (kg)", value=rider["weight"], min_value=30.0, max_value=200.0, step=0.5)
        new_hr_rest = st.number_input("FC repos", value=rider["hr_rest"], min_value=30, max_value=100, step=1)
        new_hr_max = st.number_input("FC max", value=rider["hr_max"], min_value=120, max_value=220, step=1)

        if st.button("💾 Sauvegarder profil"):
            st.session_state["ftp"] = new_ftp
            st.session_state["weight"] = new_weight
            st.session_state["hr_rest"] = new_hr_rest
            st.session_state["hr_max"] = new_hr_max
            load_data.clear()
            st.success("Profil mis à jour !")

        st.markdown("---")

        # Garmin sync
        st.markdown("**Garmin Connect**")
        st.caption("Email/mot de passe via variables d'env GARMIN_EMAIL & GARMIN_PASSWORD")
        if st.button("🔄 Synchroniser Garmin"):
            with st.spinner("Connexion Garmin…"):
                try:
                    status, client, client_state = login_step1()
                    if status == "needs_mfa":
                        st.session_state["garmin_mfa_pending"] = True
                        st.session_state["garmin_client"] = client
                        st.session_state["garmin_client_state"] = client_state
                        st.info("Code MFA requis.")
                    else:
                        ftp = st.session_state.get("ftp", 250)
                        weight = st.session_state.get("weight", 75)
                        sync_recent(client=client, ftp=ftp, weight_kg=weight)
                        load_data.clear()
                        st.success("Sync Garmin OK !")
                except Exception as ex:
                    st.error(f"Erreur : {ex}")

        if st.session_state.get("garmin_mfa_pending"):
            mfa_code = st.text_input("Code MFA", key="garmin_mfa")
            if st.button("Valider MFA"):
                try:
                    client = login_step2_mfa(
                        st.session_state["garmin_client"],
                        st.session_state["garmin_client_state"],
                        mfa_code,
                    )
                    ftp = st.session_state.get("ftp", 250)
                    weight = st.session_state.get("weight", 75)
                    sync_recent(client=client, ftp=ftp, weight_kg=weight)
                    load_data.clear()
                    st.session_state["garmin_mfa_pending"] = False
                    st.success("Sync Garmin OK !")
                except Exception as ex:
                    st.error(f"Erreur MFA : {ex}")

        st.markdown("---")

        # Strava sync
        st.markdown("**Strava**")
        if strava_sync.is_connected():
            st.success("Strava connecté ✓")
            if st.button("🔄 Sync Strava"):
                with st.spinner("Sync Strava…"):
                    sync_strava()
                    load_data.clear()
                    st.success("Sync Strava OK !")
        else:
            try:
                auth_url = strava_sync.get_auth_url("http://localhost:8501")
                st.markdown(f"[Connecter Strava]({auth_url})")
            except Exception:
                st.info("Configurez STRAVA_CLIENT_ID et STRAVA_CLIENT_SECRET.")

        st.markdown("---")

        # File import
        st.markdown("**Import fichier**")
        uploaded = st.file_uploader("FIT / GPX / TCX", type=["fit", "gpx", "tcx"], key="file_upload_sidebar")
        if uploaded:
            import hashlib
            raw_bytes = uploaded.read()
            file_hash = hashlib.sha256(raw_bytes).hexdigest()
            uploaded.seek(0)
            conn = db.get_conn()
            if db.file_already_imported(conn, file_hash):
                st.info("Fichier déjà importé.")
            else:
                with st.spinner("Import en cours…"):
                    try:
                        rec_df = parse_file(uploaded)
                        summary = extract_summary_from_df(rec_df)
                        activity_id = db.next_activity_id(conn)
                        summary["activity_id"] = activity_id
                        summary["source"] = "file"
                        summary["raw_json"] = json.dumps({"filename": uploaded.name})
                        db.upsert_activity(conn, summary)
                        db.save_ride_file(conn, activity_id, uploaded.name,
                                          uploaded.name.rsplit(".", 1)[-1].lower(), file_hash)
                        load_data.clear()
                        st.success(f"✅ Importé : {uploaded.name}")
                    except Exception as ex:
                        st.error(f"Erreur import : {ex}")
            conn.close()


# ════════════════════════════════════════════════════════════════════════════
#  LOAD DATA
# ════════════════════════════════════════════════════════════════════════════

df_all = load_data()
rider = get_rider_profile()
ftp = rider["ftp"]
weight = rider["weight"]

# Computed columns
if not df_all.empty:
    if "watts_per_kg" not in df_all.columns or df_all["watts_per_kg"].isna().all():
        df_all["watts_per_kg"] = df_all["avg_power_w"] / weight if weight > 0 else np.nan
    if "start_time" in df_all.columns:
        df_all["date"] = pd.to_datetime(df_all["start_time"]).dt.date


# ════════════════════════════════════════════════════════════════════════════
#  DEMO DATA (fallbacks quand la DB est vide)
# ════════════════════════════════════════════════════════════════════════════

DEMO_ACTIVITIES = [
    {"id": "a1", "date": "2 nov.", "title": "Sortie endurance forêt de Sénart", "source": "Garmin",
     "type": "Gravel", "km": 68.4, "dplus": 420, "duration_s": 9720, "np": 218, "avgP": 195,
     "hr": 142, "tss": 145, "ifac": 0.81, "speed": 25.3},
    {"id": "a2", "date": "30 oct.", "title": "Intervalles côte de Chevreuse", "source": "Garmin",
     "type": "Route", "km": 52.1, "dplus": 680, "duration_s": 7200, "np": 242, "avgP": 224,
     "hr": 156, "tss": 168, "ifac": 0.90, "speed": 26.1},
    {"id": "a3", "date": "28 oct.", "title": "Zwift — Tempo Watopia", "source": "Zwift",
     "type": "Indoor", "km": 40.0, "dplus": 320, "duration_s": 5400, "np": 232, "avgP": 220,
     "hr": 148, "tss": 120, "ifac": 0.87, "speed": 26.7},
    {"id": "a4", "date": "25 oct.", "title": "Gravel Fontainebleau — Milly loop", "source": "Garmin",
     "type": "Gravel", "km": 82.3, "dplus": 540, "duration_s": 12600, "np": 205, "avgP": 188,
     "hr": 138, "tss": 175, "ifac": 0.76, "speed": 23.5},
    {"id": "a5", "date": "22 oct.", "title": "Sortie bikepacking Morvan J1", "source": "Garmin",
     "type": "Bikepacking", "km": 112.0, "dplus": 1450, "duration_s": 21600, "np": 178, "avgP": 162,
     "hr": 132, "tss": 220, "ifac": 0.66, "speed": 18.7},
    {"id": "a6", "date": "19 oct.", "title": "Zwift race — Innsbruck", "source": "Zwift",
     "type": "Indoor", "km": 32.0, "dplus": 580, "duration_s": 3600, "np": 258, "avgP": 248,
     "hr": 168, "tss": 95, "ifac": 0.96, "speed": 32.0},
]

DEMO_FTP_HISTORY = [
    {"month": "Mai", "ftp": 242}, {"month": "Juin", "ftp": 248}, {"month": "Juil", "ftp": 251},
    {"month": "Août", "ftp": 255}, {"month": "Sep", "ftp": 262}, {"month": "Oct", "ftp": 268},
]

DEMO_LOAD = [
    {"week": "S36", "ctl": 52, "atl": 45, "tsb": 7},
    {"week": "S37", "ctl": 54, "atl": 55, "tsb": -1},
    {"week": "S38", "ctl": 56, "atl": 62, "tsb": -6},
    {"week": "S39", "ctl": 58, "atl": 50, "tsb": 8},
    {"week": "S40", "ctl": 61, "atl": 58, "tsb": 3},
    {"week": "S41", "ctl": 63, "atl": 70, "tsb": -7},
    {"week": "S42", "ctl": 66, "atl": 65, "tsb": 1},
    {"week": "S43", "ctl": 69, "atl": 75, "tsb": -6},
    {"week": "S44", "ctl": 71, "atl": 74, "tsb": -3},
]

DEMO_POWER_CURVE = [
    {"dur": "5s", "now": 945, "prev": 910},
    {"dur": "30s", "now": 610, "prev": 595},
    {"dur": "1min", "now": 455, "prev": 440},
    {"dur": "5min", "now": 322, "prev": 310},
    {"dur": "20min", "now": 282, "prev": 272},
    {"dur": "60min", "now": 259, "prev": 251},
]

DEMO_ZONES = [
    {"zone": "Z1", "pct": 14}, {"zone": "Z2", "pct": 46}, {"zone": "Z3", "pct": 21},
    {"zone": "Z4", "pct": 12}, {"zone": "Z5", "pct": 5}, {"zone": "Z6+", "pct": 2},
]

DEMO_GOALS = [
    {"title": "Traversée du Massif central", "desc": "480 km · 8 200 m D+ · 5 jours", "pct": 38, "featured": True},
    {"title": "FTP 285 W", "desc": "Actuel : 268 W → objectif : 285 W", "pct": 60, "featured": False},
    {"title": "Endurance 6 h Z2", "desc": "Tenir 6h en zone 2 sans décrocher", "pct": 68, "featured": False},
]

DEMO_WEEK = [
    {"day": "Lun", "desc": "Repos ou mobilité 30 min", "rest": True},
    {"day": "Mar", "desc": "Intervalles 5×5 min Z4, récup 3 min", "rest": False},
    {"day": "Mer", "desc": "Endurance Z2 — 1h30", "rest": False},
    {"day": "Jeu", "desc": "Repos", "rest": True},
    {"day": "Ven", "desc": "Tempo Z3 — 1h15 avec 2×15 min", "rest": False},
    {"day": "Sam", "desc": "Sortie longue Z2 — 3h gravel", "rest": False},
    {"day": "Dim", "desc": "Récupération active 1h facile", "rest": False},
]


def get_last_ride():
    """Return the last ride data (real or demo)."""
    if not df_all.empty:
        last = df_all.iloc[-1]
        return {
            "title": last.get("name", "Dernière sortie"),
            "date": str(last.get("start_time", ""))[:10],
            "source": last.get("source", "Garmin"),
            "type": last.get("activity_type", "Gravel"),
            "km": last.get("distance_m", 0) / 1000 if last.get("distance_m") else 0,
            "dplus": last.get("elevation_gain_m", 0),
            "duration_s": last.get("duration_s", 0),
            "np": last.get("normalized_power_w", 0),
            "avgP": last.get("avg_power_w", 0),
            "hr": last.get("avg_hr", 0),
            "tss": last.get("tss", 0),
            "ifac": last.get("intensity_factor", 0),
            "speed": last.get("avg_speed_kmh", 0),
        }
    return DEMO_ACTIVITIES[0]


def get_pmc_data():
    """Return PMC data (real or demo)."""
    if not df_all.empty and "tss" in df_all.columns:
        tss_col = df_all.dropna(subset=["tss"])
        if not tss_col.empty and "date" in tss_col.columns:
            daily = tss_col.groupby("date")["tss"].sum()
            daily.index = pd.to_datetime(daily.index)
            if len(daily) >= 7:
                pmc = performance_management_chart(daily)
                return pmc
    # Demo fallback
    return pd.DataFrame(DEMO_LOAD)


def get_ftp_history():
    """Return FTP history (real or demo)."""
    ftp_df = db.load_ftp_history()
    if not ftp_df.empty:
        return ftp_df
    return pd.DataFrame(DEMO_FTP_HISTORY)


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — TABLEAU DE BORD
# ════════════════════════════════════════════════════════════════════════════

if page == "🏠  Tableau de bord":
    # Page title with kicker
    today = dt.datetime.now()
    day_names_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    month_names_fr = ["janvier", "février", "mars", "avril", "mai", "juin",
                      "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    day_name = day_names_fr[today.weekday()]
    month_name = month_names_fr[today.month - 1]

    # Get PMC for TSB
    pmc = get_pmc_data()
    if isinstance(pmc, pd.DataFrame) and "tsb" in pmc.columns and len(pmc) > 0:
        current_tsb = pmc["tsb"].iloc[-1]
        current_ctl = pmc["ctl"].iloc[-1] if "ctl" in pmc.columns else 71
    else:
        current_tsb = -3
        current_ctl = 71

    if current_tsb > 5:
        form_msg = "tu es en pleine forme !"
    elif current_tsb > -5:
        form_msg = "tu es en bonne forme."
    elif current_tsb > -15:
        form_msg = "attention à la fatigue."
    else:
        form_msg = "repos recommandé."

    st.markdown(f"""
    <div class="gc-kicker">{day_name} {today.day} {month_name}</div>
    <div class="gc-page-title">Salut {rider['name']}, {form_msg}</div>
    """, unsafe_allow_html=True)

    # ── Coach recommendation card ──
    st.markdown("""
    <div class="gc-coach-reco">
        <div class="gc-coach-reco-title">✨ Recommandation du coach</div>
        <div class="gc-coach-reco-text">
            Ta forme est bonne avec un TSB légèrement négatif — c'est le signe d'une charge
            d'entraînement productive. Continue sur ce rythme en gardant 2-3 sorties Z2
            longues par semaine. Prochaine étape : une session d'intervalles Z4 mardi.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 4 KPI stats ──
    wpkg = ftp / weight if weight > 0 else 0
    ctl_delta = 8  # delta par défaut
    if isinstance(pmc, pd.DataFrame) and "ctl" in pmc.columns and len(pmc) > 14:
        ctl_delta = round(pmc["ctl"].iloc[-1] - pmc["ctl"].iloc[-14], 0)

    tsb_label = "Fatigue modérée" if current_tsb < 0 else "Bonne forme"

    cols_kpi = st.columns(4)
    with cols_kpi[0]:
        st.markdown(stat_html("FTP", f"{ftp}", "W", delta=6, delta_suffix=""), unsafe_allow_html=True)
    with cols_kpi[1]:
        st.markdown(stat_html("W/kg", f"{wpkg:.2f}", "", delta=0.08, delta_suffix=""), unsafe_allow_html=True)
    with cols_kpi[2]:
        st.markdown(stat_html("Fitness · CTL", f"{int(current_ctl)}", "", delta=int(ctl_delta), delta_suffix=""), unsafe_allow_html=True)
    with cols_kpi[3]:
        st.markdown(f"""
        <div class="gc-stat">
            <div class="gc-stat-label">FORME · TSB</div>
            <div class="gc-stat-row">
                <span class="gc-stat-value">{int(current_tsb)}</span>
                <span class="gc-stat-unit" style="color:{'#6db56d' if current_tsb > 0 else '#c45a5a'}">{tsb_label}</span>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Charts: CTL/ATL + FTP History ──
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown(section_start("Charge d'entraînement"), unsafe_allow_html=True)
        fig_pmc = make_plotly_fig(height=260)
        if isinstance(pmc, pd.DataFrame) and "ctl" in pmc.columns:
            x_col = "date" if "date" in pmc.columns else "week"
            fig_pmc.add_trace(go.Scatter(x=pmc[x_col], y=pmc["ctl"], name="CTL (Fitness)",
                                         fill="tozeroy", fillcolor="rgba(196,135,58,0.15)",
                                         line=dict(color=C["chart1"], width=2)))
            fig_pmc.add_trace(go.Scatter(x=pmc[x_col], y=pmc["atl"], name="ATL (Fatigue)",
                                         fill="tozeroy", fillcolor="rgba(109,181,109,0.1)",
                                         line=dict(color=C["chart2"], width=2)))
        fig_pmc.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        st.plotly_chart(fig_pmc, use_container_width=True, config={"displayModeBar": False})
        st.markdown(section_end(), unsafe_allow_html=True)

    with col_chart2:
        st.markdown(section_start("Évolution FTP"), unsafe_allow_html=True)
        ftp_hist = get_ftp_history()
        fig_ftp = make_plotly_fig(height=260)
        if "month" in ftp_hist.columns:
            fig_ftp.add_trace(go.Scatter(x=ftp_hist["month"], y=ftp_hist["ftp"], name="FTP",
                                          mode="lines+markers",
                                          line=dict(color=C["chart1"], width=2.5),
                                          marker=dict(size=7, color=C["chart1"])))
        elif "date" in ftp_hist.columns:
            fig_ftp.add_trace(go.Scatter(x=ftp_hist["date"], y=ftp_hist["ftp_w"], name="FTP",
                                          mode="lines+markers",
                                          line=dict(color=C["chart1"], width=2.5),
                                          marker=dict(size=7, color=C["chart1"])))
        fig_ftp.update_layout(showlegend=False)
        st.plotly_chart(fig_ftp, use_container_width=True, config={"displayModeBar": False})
        st.markdown(section_end(), unsafe_allow_html=True)

    # ── Dernière sortie ──
    last = get_last_ride()
    st.markdown(section_start("Dernière sortie"), unsafe_allow_html=True)
    st.markdown(f"""
    <div style="margin-bottom:16px">
        <div style="font-family:'Archivo',sans-serif;font-weight:600;font-size:1rem;color:{C['text']}">{last['title']}</div>
        <div style="font-size:0.75rem;color:{C['text_m']};margin-top:2px">{last['date']} · {last['source']} · {last['type']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="gc-ride-detail-grid">', unsafe_allow_html=True)
    ride_items = [
        ("Distance", f"{last['km']:.1f}", "km"),
        ("Dénivelé", f"{int(last['dplus'])}", "m"),
        ("Durée", fmt_duration(last['duration_s']), ""),
        ("Puissance NP", f"{int(last['np'])}", "W"),
        ("FC moyenne", f"{int(last['hr'])}", "bpm"),
        ("TSS", f"{int(last['tss'])}", ""),
    ]
    for lbl, val, unit in ride_items:
        st.markdown(f"""
        <div class="gc-ride-detail-item">
            <div style="font-size:0.65rem;color:{C['text_m']};text-transform:uppercase;letter-spacing:0.1em">{lbl}</div>
            <div style="display:flex;align-items:baseline;gap:4px;margin-top:4px">
                <span style="font-family:'JetBrains Mono',monospace;font-size:1.15rem;color:{C['text']}">{val}</span>
                <span style="font-size:0.7rem;color:{C['text_m']}">{unit}</span>
            </div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(section_end(), unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — ACTIVITÉS
# ════════════════════════════════════════════════════════════════════════════

elif page == "🚴  Activités":
    st.markdown("""
    <div class="gc-kicker">HISTORIQUE</div>
    <div class="gc-page-title">Activités</div>
    """, unsafe_allow_html=True)

    # Filter pills
    if "activity_filter" not in st.session_state:
        st.session_state["activity_filter"] = "Tout"

    filter_options = ["Tout", "Gravel", "Route", "Indoor", "Bikepacking"]
    cols_filter = st.columns(len(filter_options) + 1)
    for i, f in enumerate(filter_options):
        with cols_filter[i]:
            cls = "gc-pill gc-pill-active" if st.session_state["activity_filter"] == f else "gc-pill"
            if st.button(f, key=f"filter_{f}", use_container_width=True):
                st.session_state["activity_filter"] = f
                st.rerun()

    # Import button in last column
    with cols_filter[-1]:
        uploaded_act = st.file_uploader("📤 Importer", type=["fit", "gpx", "tcx"],
                                        key="file_upload_activities", label_visibility="collapsed")
        if uploaded_act:
            import hashlib
            raw_bytes = uploaded_act.read()
            file_hash = hashlib.sha256(raw_bytes).hexdigest()
            uploaded_act.seek(0)
            conn = db.get_conn()
            if not db.file_already_imported(conn, file_hash):
                try:
                    rec_df = parse_file(uploaded_act)
                    summary = extract_summary_from_df(rec_df)
                    activity_id = db.next_activity_id(conn)
                    summary["activity_id"] = activity_id
                    summary["source"] = "file"
                    summary["raw_json"] = json.dumps({"filename": uploaded_act.name})
                    db.upsert_activity(conn, summary)
                    db.save_ride_file(conn, activity_id, uploaded_act.name,
                                      uploaded_act.name.rsplit(".", 1)[-1].lower(), file_hash)
                    load_data.clear()
                    st.success(f"✅ Importé : {uploaded_act.name}")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Erreur : {ex}")
            else:
                st.info("Fichier déjà importé.")
            conn.close()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Activity list
    current_filter = st.session_state.get("activity_filter", "Tout")

    if not df_all.empty:
        # Use real data
        display_df = df_all.copy().sort_values("start_time", ascending=False)
        if current_filter != "Tout":
            filter_map = {
                "Gravel": ["cycling", "gravel", "mountain_biking"],
                "Route": ["road_cycling", "cycling"],
                "Indoor": ["indoor_cycling", "virtual_ride"],
                "Bikepacking": ["cycling"],  # filtered by name
            }
            if current_filter == "Indoor":
                display_df = display_df[display_df["category"].isin(["indoor", "indoor_zwift"])]
            elif current_filter == "Bikepacking":
                display_df = display_df[display_df["name"].str.lower().str.contains("bikepacking|bivouac|multi", na=False)]
            else:
                display_df = display_df[display_df["category"] == "outdoor"]

        for _, row in display_df.head(20).iterrows():
            name = row.get("name", "Activité")
            date_str = str(row.get("start_time", ""))[:10]
            source = row.get("source", "garmin").capitalize()
            atype = row.get("activity_type", "Cycling")
            km = row.get("distance_m", 0) / 1000 if row.get("distance_m") else 0
            dplus = row.get("elevation_gain_m", 0) or 0
            dur = fmt_duration(row.get("duration_s"))
            np_w = int(row.get("normalized_power_w", 0) or 0)
            tss_val = int(row.get("tss", 0) or 0)

            st.markdown(f"""
            <div class="gc-activity-row">
                <div>
                    <div class="gc-activity-title">{name}</div>
                    <div class="gc-activity-meta">{date_str} · {source} · {atype}</div>
                </div>
                <div class="gc-activity-stats">
                    <div><div class="gc-activity-stat-val">{km:.1f} km</div><div class="gc-activity-stat-lbl">Distance</div></div>
                    <div><div class="gc-activity-stat-val">{int(dplus)} m</div><div class="gc-activity-stat-lbl">D+</div></div>
                    <div><div class="gc-activity-stat-val">{dur}</div><div class="gc-activity-stat-lbl">Durée</div></div>
                    <div><div class="gc-activity-stat-val">{np_w} W</div><div class="gc-activity-stat-lbl">NP</div></div>
                    <div><div class="gc-activity-stat-val">{tss_val}</div><div class="gc-activity-stat-lbl">TSS</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        # Demo data
        activities_to_show = DEMO_ACTIVITIES if current_filter == "Tout" else [
            a for a in DEMO_ACTIVITIES if a["type"] == current_filter
        ]
        for a in activities_to_show:
            st.markdown(f"""
            <div class="gc-activity-row">
                <div>
                    <div class="gc-activity-title">{a['title']}</div>
                    <div class="gc-activity-meta">{a['date']} · {a['source']} · {a['type']}</div>
                </div>
                <div class="gc-activity-stats">
                    <div><div class="gc-activity-stat-val">{a['km']:.1f} km</div><div class="gc-activity-stat-lbl">Distance</div></div>
                    <div><div class="gc-activity-stat-val">{int(a['dplus'])} m</div><div class="gc-activity-stat-lbl">D+</div></div>
                    <div><div class="gc-activity-stat-val">{fmt_duration(a['duration_s'])}</div><div class="gc-activity-stat-lbl">Durée</div></div>
                    <div><div class="gc-activity-stat-val">{int(a['np'])} W</div><div class="gc-activity-stat-lbl">NP</div></div>
                    <div><div class="gc-activity-stat-val">{int(a['tss'])}</div><div class="gc-activity-stat-lbl">TSS</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Activity detail (when selected) ──
    st.markdown("<hr class='gc-divider'>", unsafe_allow_html=True)

    if not df_all.empty:
        activity_names = df_all.sort_values("start_time", ascending=False)["name"].dropna().tolist()
        if activity_names:
            selected_name = st.selectbox("🔍 Détail d'une sortie", ["—"] + activity_names[:20])
            if selected_name != "—":
                sel = df_all[df_all["name"] == selected_name].iloc[0]
                aid = sel["activity_id"]

                st.markdown(f"""
                <div style="margin:16px 0">
                    <div class="gc-page-title" style="font-size:1.3rem">{selected_name}</div>
                </div>
                """, unsafe_allow_html=True)

                # 8 stat cards in 2×4 grid
                detail_stats = [
                    ("Distance", f"{sel.get('distance_m',0)/1000:.1f}", "km"),
                    ("Dénivelé", f"{int(sel.get('elevation_gain_m',0) or 0)}", "m D+"),
                    ("Puissance NP", f"{int(sel.get('normalized_power_w',0) or 0)}", "W"),
                    ("IF / TSS", f"{(sel.get('intensity_factor',0) or 0):.2f} / {int(sel.get('tss',0) or 0)}", ""),
                    ("Durée", fmt_duration(sel.get('duration_s')), ""),
                    ("Vitesse", f"{(sel.get('avg_speed_kmh',0) or 0):.1f}", "km/h"),
                    ("FC", f"{int(sel.get('avg_hr',0) or 0)}", "bpm"),
                    ("Calories", f"{int(sel.get('calories',0) or 0)}", "kcal (est.)"),
                ]
                cols_det = st.columns(4)
                for i, (lbl, val, unit) in enumerate(detail_stats):
                    with cols_det[i % 4]:
                        st.markdown(f"""
                        <div class="gc-card-muted" style="margin-bottom:8px">
                            <div style="font-size:0.65rem;color:{C['text_m']};text-transform:uppercase;letter-spacing:0.1em">{lbl}</div>
                            <div style="display:flex;align-items:baseline;gap:4px;margin-top:4px">
                                <span class="mono" style="font-size:1.15rem;color:{C['text']}">{val}</span>
                                <span style="font-size:0.7rem;color:{C['text_m']}">{unit}</span>
                            </div>
                        </div>""", unsafe_allow_html=True)

                # Ride detail chart (from ride_detail module)
                try:
                    render_ride_analysis(int(aid), ftp)
                except Exception:
                    pass


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — PERFORMANCE
# ════════════════════════════════════════════════════════════════════════════

elif page == "📊  Performance":
    st.markdown("""
    <div class="gc-kicker">ANALYSE</div>
    <div class="gc-page-title">Performance</div>
    """, unsafe_allow_html=True)

    # ── 4 top stats ──
    cols_perf = st.columns(4)
    with cols_perf[0]:
        st.markdown(stat_html("FTP MESURÉ", str(ftp), "W"), unsafe_allow_html=True)
    with cols_perf[1]:
        st.markdown(stat_html("VO2MAX", str(rider["vo2max"]), "", delta=None), unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:0.65rem;color:{C["text_m"]}">estimé</div>', unsafe_allow_html=True)
    with cols_perf[2]:
        st.markdown(stat_html("FC REPOS", str(rider["hr_rest"]), "bpm"), unsafe_allow_html=True)
    with cols_perf[3]:
        st.markdown(stat_html("FC MAX", str(rider["hr_max"]), "bpm"), unsafe_allow_html=True)

    ftp_hist = get_ftp_history()
    if "date" in ftp_hist.columns:
        src_note = f"Test 20 min · dernière mesure {ftp_hist['date'].iloc[-1]}"
    else:
        src_note = "Test 20 min Zwift · 12 oct."
    st.markdown(f'<div style="font-size:0.75rem;color:{C["text_m"]};margin:8px 0 20px 0">Source : {src_note}</div>', unsafe_allow_html=True)

    # ── Power Curve + W/kg charts ──
    col_pc, col_wkg = st.columns(2)

    with col_pc:
        st.markdown(section_start("Courbe de puissance"), unsafe_allow_html=True)
        fig_pc = make_plotly_fig(height=280)
        pc_data = DEMO_POWER_CURVE
        # Try real data from DB
        best_pc = db.load_best_power_curve()
        if not best_pc.empty:
            dur_labels = {5: "5s", 30: "30s", 60: "1min", 300: "5min", 1200: "20min", 3600: "60min"}
            fig_pc.add_trace(go.Scatter(
                x=[dur_labels.get(d, f"{d}s") for d in best_pc["duration_s"]],
                y=best_pc["power_w"],
                name="Meilleur", mode="lines+markers",
                line=dict(color=C["chart1"], width=2.5),
                marker=dict(size=7, color=C["chart1"]),
            ))
        else:
            fig_pc.add_trace(go.Scatter(
                x=[p["dur"] for p in pc_data], y=[p["now"] for p in pc_data],
                name="Actuel", mode="lines+markers",
                line=dict(color=C["chart1"], width=2.5),
                marker=dict(size=7, color=C["chart1"]),
            ))
            fig_pc.add_trace(go.Scatter(
                x=[p["dur"] for p in pc_data], y=[p["prev"] for p in pc_data],
                name="Précédent", mode="lines",
                line=dict(color=C["text_m"], width=1.5, dash="dash"),
            ))
        fig_pc.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        st.plotly_chart(fig_pc, use_container_width=True, config={"displayModeBar": False})
        st.markdown(section_end(), unsafe_allow_html=True)

    with col_wkg:
        st.markdown(section_start("Watts par kilo"), unsafe_allow_html=True)
        fig_wkg = make_plotly_fig(height=280)
        if not best_pc.empty and weight > 0:
            dur_labels = {5: "5s", 30: "30s", 60: "1min", 300: "5min", 1200: "20min", 3600: "60min"}
            wkg_vals = best_pc["power_w"] / weight
            fig_wkg.add_trace(go.Bar(
                x=[dur_labels.get(d, f"{d}s") for d in best_pc["duration_s"]],
                y=wkg_vals,
                marker_color=C["chart1"],
                marker_line_width=0,
            ))
        else:
            durs = [p["dur"] for p in pc_data]
            wkg_vals = [p["now"] / weight for p in pc_data]
            fig_wkg.add_trace(go.Bar(
                x=durs, y=wkg_vals,
                marker_color=C["chart1"],
                marker_line_width=0,
            ))
        fig_wkg.update_layout(showlegend=False, yaxis_title="W/kg")
        st.plotly_chart(fig_wkg, use_container_width=True, config={"displayModeBar": False})
        st.markdown(section_end(), unsafe_allow_html=True)

    # ── Records ──
    st.markdown(section_start("Records personnels"), unsafe_allow_html=True)
    records_data = DEMO_POWER_CURVE
    if not best_pc.empty:
        dur_map = {5: "5s", 30: "30s", 60: "1min", 300: "5min", 1200: "20min", 3600: "60min"}
        records_data = [{"dur": dur_map.get(int(r["duration_s"]), f"{int(r['duration_s'])}s"),
                         "now": int(r["power_w"]), "prev": None}
                        for _, r in best_pc.iterrows() if int(r["duration_s"]) in dur_map]

    st.markdown('<div class="gc-records-grid">', unsafe_allow_html=True)
    for rec in records_data:
        delta_str = ""
        if rec.get("prev") and rec["prev"] > 0:
            d = rec["now"] - rec["prev"]
            delta_str = f'<div class="gc-record-delta">+{d} W</div>' if d > 0 else ""
        st.markdown(f"""
        <div class="gc-record-item">
            <div>
                <div class="gc-record-label">{rec['dur']}</div>
                {delta_str}
            </div>
            <div class="gc-record-value">{rec['now']} W</div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(section_end(), unsafe_allow_html=True)

    # ── Zones (30 jours) ──
    st.markdown(section_start("Zones de puissance (30 jours)"), unsafe_allow_html=True)

    # Compute zone distribution from recent activities
    zone_data = DEMO_ZONES
    if not df_all.empty:
        recent_30 = df_all[df_all["start_time"] >= (pd.Timestamp.now() - pd.Timedelta(days=30))]
        # If we have zone data from individual activities, compute; otherwise use demo
        # For now use demo as zone computation requires per-second data

    for z in zone_data:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
            <div style="min-width:36px;font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:{C['text_m']}">{z['zone']}</div>
            <div class="gc-zone-bar-track" style="flex:1">
                <div class="gc-zone-bar-fill" style="width:{z['pct']}%"></div>
            </div>
            <div style="min-width:36px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:{C['text']}">{z['pct']}%</div>
        </div>""", unsafe_allow_html=True)
    st.markdown(section_end(), unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 4 — COACH IA
# ════════════════════════════════════════════════════════════════════════════

elif page == "💬  Coach IA":
    st.markdown("""
    <div class="gc-kicker">ASSISTANT</div>
    <div class="gc-page-title">Coach IA</div>
    """, unsafe_allow_html=True)

    col_chat, col_prog = st.columns([2, 1])

    with col_chat:
        st.markdown(section_start("Conversation"), unsafe_allow_html=True)

        # Initialize chat history
        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = [
                {"role": "ai", "text": f"Salut {rider['name']} ! Ta forme actuelle est bonne — "
                 f"ton CTL est en progression régulière. Avec un TSB légèrement négatif, "
                 f"tu absorbes bien la charge. Qu'est-ce que tu veux travailler ?"},
            ]

        # Display messages
        for msg in st.session_state["chat_messages"]:
            cls = "gc-chat-me" if msg["role"] == "me" else "gc-chat-ai"
            st.markdown(f'<div class="{cls}">{msg["text"]}</div>', unsafe_allow_html=True)

        # Suggestion chips
        suggestions = [
            "Préparer la Traversée du Massif central",
            "Plan pour augmenter ma FTP",
            "Analyse de ma dernière sortie",
            "Nutrition pour sortie longue",
        ]
        st.markdown('<div style="margin-top:12px">', unsafe_allow_html=True)
        for sug in suggestions:
            st.markdown(f'<span class="gc-chip">{sug}</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Input
        user_input = st.text_input("Message", placeholder="Pose une question au coach…",
                                   key="coach_input", label_visibility="collapsed")
        col_send, _ = st.columns([1, 4])
        with col_send:
            send = st.button("Envoyer", key="send_coach")

        if send and user_input:
            st.session_state["chat_messages"].append({"role": "me", "text": user_input})
            with st.spinner("Le coach réfléchit…"):
                try:
                    report = generate_coach_report(
                        activities_df=df_all,
                        ftp=ftp,
                        weight=weight,
                        question=user_input,
                    )
                    answer = report.summary if hasattr(report, "summary") else str(report)
                except Exception:
                    answer = ("Je suis ton coach IA. Pour le moment, je fonctionne en mode démo. "
                              "Connecte ton compte Garmin ou Strava pour une analyse personnalisée !")
            st.session_state["chat_messages"].append({"role": "ai", "text": answer})
            st.rerun()

        st.markdown(section_end(), unsafe_allow_html=True)

    with col_prog:
        st.markdown(section_start("Programme de la semaine"), unsafe_allow_html=True)
        for day in DEMO_WEEK:
            if day["rest"]:
                st.markdown(f"""
                <div class="gc-week-day">
                    <div class="gc-week-day-label">{day['day']}</div>
                    <div class="gc-week-day-rest">{day['desc']}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="gc-week-day">
                    <div class="gc-week-day-label">{day['day']}</div>
                    <div class="gc-week-day-desc">{day['desc']}</div>
                </div>""", unsafe_allow_html=True)
        st.markdown(section_end(), unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 5 — OBJECTIFS
# ════════════════════════════════════════════════════════════════════════════

elif page == "⛰️  Objectifs":
    st.markdown("""
    <div class="gc-kicker">PROGRESSION</div>
    <div class="gc-page-title">Objectifs</div>
    """, unsafe_allow_html=True)

    # ── Goal cards ──
    for i, goal in enumerate(DEMO_GOALS):
        card_class = "gc-goal-card-featured" if goal.get("featured") else "gc-goal-card"
        st.markdown(f"""
        <div class="{card_class}" style="margin-bottom:16px">
            <div style="font-family:'Archivo',sans-serif;font-weight:700;font-size:1.05rem;color:{C['text']};margin-bottom:4px;position:relative">
                {goal['title']}
            </div>
            <div style="font-size:0.8rem;color:{C['text_m']};margin-bottom:12px;position:relative">{goal['desc']}</div>
            <div style="display:flex;align-items:center;gap:12px;position:relative">
                <div class="gc-progress-track" style="flex:1">
                    <div class="gc-progress-fill" style="width:{goal['pct']}%"></div>
                </div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;color:{C['primary']}">{goal['pct']}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Prep checklist ──
    st.markdown(section_start("Préparation — Traversée du Massif central"), unsafe_allow_html=True)
    prep_items = [
        ("Tenir 4h en Z2 sans décrocher", True),
        ("Enchaîner 2 jours > 100 km", True),
        ("Test nutrition (500 kcal/h)", False),
        ("Reconnaissance col du Puy Mary", False),
        ("FTP ≥ 280 W", False),
    ]
    for label, done in prep_items:
        icon_cls = "gc-check-done" if done else "gc-check-pending"
        icon_txt = "✓" if done else ""
        text_color = C["text"] if done else C["text_m"]
        st.markdown(f"""
        <div class="gc-checklist-row">
            <div class="gc-check-icon {icon_cls}">{icon_txt}</div>
            <div style="font-size:0.85rem;color:{text_color}">{label}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown(section_end(), unsafe_allow_html=True)

    # ── New goal buttons ──
    st.markdown(section_start("Nouvel objectif"), unsafe_allow_html=True)
    new_goal_options = [
        ("🏔️", "Événement gravel"),
        ("⚡", "Objectif puissance"),
        ("🏋️", "Endurance"),
        ("📉", "Perte de poids"),
        ("🗓️", "Volume hebdo"),
        ("🎯", "Objectif libre"),
    ]
    cols_goals = st.columns(3)
    for i, (icon, label) in enumerate(new_goal_options):
        with cols_goals[i % 3]:
            st.markdown(f"""
            <div class="gc-new-goal">
                <div class="gc-new-goal-icon">{icon}</div>
                <div class="gc-new-goal-text">{label}</div>
            </div>""", unsafe_allow_html=True)
    st.markdown(section_end(), unsafe_allow_html=True)
