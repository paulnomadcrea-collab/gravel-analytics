"""
Gravel Coach v6 — Dashboard unifié indoor/outdoor/Zwift.
Design light « Clean White » inspiré d'un dashboard cycling Pinterest fond blanc.

Lancer en local :
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import db
from analysis import (
    DEFAULT_ZONES,
    performance_management_chart,
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

# ───────────────────────── CSS — Clean White Light Theme ─────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    /* ─── Clean White palette (Pinterest cycling dashboard) ─── */
    --bg-main:        #F8FAFB;
    --bg-card:        #FFFFFF;
    --bg-sidebar:     #1B2432;
    --bg-muted:       #F1F5F9;
    --bg-elevated:    #FFFFFF;
    --border:         #E2E8F0;
    --border-light:   #CBD5E1;
    --text-primary:   #1A1A2E;
    --text-secondary: #4A5568;
    --text-muted:     #94A3B8;
    --primary:        #2D6A4F;   /* forest teal-green */
    --primary-dim:    rgba(45,106,79,0.08);
    --primary-fg:     #FFFFFF;
    --accent:         #E8914F;   /* warm orange */
    --accent-dim:     rgba(232,145,79,0.10);
    --chart-1:        #2D6A4F;   /* forest green */
    --chart-2:        #3A8F71;   /* teal */
    --chart-3:        #E8914F;   /* warm orange */
    --chart-4:        #D4783A;   /* amber */
    --chart-5:        #5B9BD5;   /* soft blue */
    --chart-6:        #7C6FAF;   /* muted purple */
    --shadow-sm:      0 1px 3px rgba(0,0,0,0.06);
    --shadow-md:      0 4px 12px rgba(0,0,0,0.08);
    --shadow-lg:      0 10px 30px rgba(0,0,0,0.10);
    --shadow-card:    0 2px 8px rgba(0,0,0,0.05);
    --radius:         16px;
    --radius-sm:      10px;
}

html, body, [class*="st-"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
h1, h2, h3, .font-display {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-weight: 800 !important;
}

/* ─── Global light background ─── */
.stApp, .main .block-container {
    background: var(--bg-main) !important;
    color: var(--text-primary) !important;
}
.stApp { background-color: var(--bg-main) !important; }
.main .block-container { max-width: 1200px !important; }

/* ─── Sidebar (dark) ─── */
section[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: none;
    box-shadow: 2px 0 12px rgba(0,0,0,0.08);
}
section[data-testid="stSidebar"] > div {
    background: var(--bg-sidebar) !important;
}
section[data-testid="stSidebar"] .stMarkdown h2 {
    color: #FFFFFF !important;
    font-weight: 800;
    font-family: 'Inter', sans-serif !important;
}
section[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #8899AA;
    margin: 1.4rem 0 0.5rem;
    font-weight: 700;
}
section[data-testid="stSidebar"] label {
    color: #B0BEC5 !important;
    font-weight: 500;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stCaption {
    color: #8899AA !important;
}

/* Sidebar inputs */
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] select,
section[data-testid="stSidebar"] .stSelectbox > div > div,
section[data-testid="stSidebar"] .stNumberInput input {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: var(--radius-sm) !important;
    color: #FFFFFF !important;
}

/* Sidebar buttons */
section[data-testid="stSidebar"] .stButton > button {
    background: var(--primary) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 700 !important;
    padding: 0.55rem 1.1rem !important;
    transition: all 0.25s ease;
    box-shadow: 0 2px 8px rgba(45,106,79,0.25);
}
section[data-testid="stSidebar"] .stButton > button:hover {
    opacity: 0.9;
    box-shadow: 0 4px 16px rgba(45,106,79,0.35);
}

/* ─── KPI cards ─── */
.kpi-row {
    display: flex;
    gap: 12px;
    margin-bottom: 1.4rem;
    flex-wrap: wrap;
}
.kpi-card {
    flex: 1;
    min-width: 140px;
    background: var(--bg-card);
    border: none;
    border-radius: var(--radius);
    padding: 20px;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-card);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--accent));
    opacity: 0;
    transition: opacity 0.25s;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
.kpi-card:hover::before { opacity: 1; }
.kpi-label {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-muted);
    margin-bottom: 8px;
    font-weight: 700;
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 900;
    font-family: 'Inter', sans-serif;
    color: var(--text-primary);
    line-height: 1;
    letter-spacing: -0.02em;
}
.kpi-value small {
    font-size: 0.45em;
    color: var(--text-muted);
    font-weight: 500;
    margin-left: 2px;
}
.kpi-sub {
    font-size: 0.72rem;
    color: var(--text-secondary);
    margin-top: 8px;
}
.kpi-delta {
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    color: var(--primary);
    margin-top: 4px;
    font-weight: 600;
}

/* ─── Category badges (pill style) ─── */
.cat-badge {
    display: inline-block;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 3px 10px;
    border-radius: 999px;
    text-transform: uppercase;
}
.cat-outdoor { background: var(--primary-dim); color: var(--primary); }
.cat-indoor  { background: var(--accent-dim); color: var(--accent); }
.cat-zwift   { background: rgba(91,155,213,0.12); color: var(--chart-5); }

/* ─── Section header ─── */
.section-header {
    font-size: 0.95rem;
    font-weight: 700;
    font-family: 'Inter', sans-serif;
    color: var(--text-primary);
    margin: 2rem 0 0.8rem;
    display: flex;
    align-items: center;
    gap: 8px;
    letter-spacing: -0.01em;
}
.section-kicker {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--primary);
    font-weight: 700;
    margin-bottom: 2px;
}

/* ─── Hide Streamlit branding ─── */
#MainMenu, footer, header { visibility: hidden; }

/* ─── Tab styling (pill-style) ─── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-card);
    border-radius: var(--radius);
    padding: 4px;
    border: none;
    box-shadow: var(--shadow-card);
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.78rem;
    padding: 8px 16px;
    color: var(--text-muted);
    letter-spacing: 0.01em;
    transition: all 0.2s;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-secondary);
    background: var(--bg-muted);
}
.stTabs [aria-selected="true"] {
    background: var(--primary) !important;
    color: #FFFFFF !important;
    font-weight: 700;
    box-shadow: 0 2px 6px rgba(45,106,79,0.2);
}
.stTabs [data-baseweb="tab-highlight"] {
    background: transparent !important;
}
.stTabs [data-baseweb="tab-border"] {
    background: transparent !important;
}

/* ─── General buttons ─── */
.stButton > button {
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    border: 1px solid var(--border) !important;
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    transition: all 0.25s ease;
    box-shadow: var(--shadow-sm);
}
.stButton > button:hover {
    border-color: var(--primary) !important;
    background: var(--bg-muted) !important;
    box-shadow: var(--shadow-md);
}

/* ─── Dataframe ─── */
.stDataFrame {
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow-card);
    border: none;
}

/* ─── Training plan card ─── */
.plan-card {
    background: var(--bg-card);
    border: none;
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 8px;
    transition: all 0.25s ease;
    box-shadow: var(--shadow-card);
}
.plan-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
.plan-card.done  { opacity: 0.5; border-left: 3px solid var(--primary); }
.plan-card.today { border-left: 3px solid var(--accent); background: var(--accent-dim); }
.plan-card.future { border-left: 3px solid var(--border); }

/* ─── Progress bar ─── */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--primary), var(--accent)) !important;
    border-radius: 6px;
}
.stProgress > div {
    background: var(--bg-muted) !important;
    border-radius: 6px;
}

/* ─── Metric styling ─── */
[data-testid="stMetric"] {
    background: var(--bg-card);
    border: none;
    border-radius: var(--radius);
    padding: 16px 20px;
    box-shadow: var(--shadow-card);
}
[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-size: 0.65rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    font-weight: 700 !important;
}
[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-weight: 900 !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
}

/* ─── Expander ─── */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border-radius: var(--radius) !important;
    border: none !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    box-shadow: var(--shadow-sm);
}
details {
    background: var(--bg-card) !important;
    border-radius: var(--radius) !important;
    border: none !important;
    box-shadow: var(--shadow-sm);
}

/* ─── Plotly ─── */
.js-plotly-plot .plotly .modebar { display: none !important; }

/* ─── Alerts / info boxes ─── */
.stAlert {
    border-radius: var(--radius) !important;
    border: none !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ─── Inputs ─── */
.stMultiSelect > div > div,
.stSelectbox > div > div {
    border-radius: var(--radius-sm) !important;
    background: var(--bg-card) !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
}
.stTextInput input {
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border) !important;
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
}
.stNumberInput input {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}

/* ─── Radio / checkbox ─── */
.stRadio label, .stCheckbox label {
    color: var(--text-secondary) !important;
}

/* ─── Markdown text ─── */
.stMarkdown, .stMarkdown p, .stCaption {
    color: var(--text-secondary) !important;
}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
    color: var(--text-primary) !important;
}
.stMarkdown strong {
    color: var(--text-primary) !important;
}

/* ─── Coach recommendation card ─── */
.coach-reco {
    background: var(--bg-card);
    border: none;
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-card);
}
.coach-reco::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    background: linear-gradient(180deg, var(--primary), var(--accent));
    border-radius: 3px 0 0 3px;
}
.coach-reco .coach-title {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    color: var(--primary);
    font-size: 0.88rem;
    margin-bottom: 6px;
}
.coach-reco .coach-text {
    color: var(--text-secondary);
    font-size: 0.85rem;
    line-height: 1.5;
}

/* ─── Comparison rows ─── */
.compare-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-muted);
    border-radius: var(--radius-sm);
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 0.85rem;
}
.compare-row .label { color: var(--text-secondary); }
.compare-row .value {
    font-family: 'JetBrains Mono', monospace;
    color: var(--primary);
    font-weight: 600;
}

/* ─── Score ring ─── */
.score-ring {
    text-align: center;
    padding: 24px;
    background: var(--bg-card);
    border-radius: var(--radius);
    border: none;
    position: relative;
    box-shadow: var(--shadow-card);
}
.score-ring .score-value {
    font-size: 3.5rem;
    font-weight: 900;
    font-family: 'Inter', sans-serif;
    color: var(--primary);
    letter-spacing: -0.03em;
}
.score-ring .score-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
}

/* ─── File uploader ─── */
[data-testid="stFileUploader"] {
    background: var(--bg-card) !important;
    border: 2px dashed var(--border) !important;
    border-radius: var(--radius) !important;
}
[data-testid="stFileUploader"] label {
    color: var(--text-secondary) !important;
}

/* ─── Scrollbar ─── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-main); }
::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* ─── Hero banner (dark card on light bg) ─── */
.hero-banner {
    background: linear-gradient(135deg, #1B2432 0%, #2D3B4E 50%, #1E3A2F 100%);
    border: none;
    border-radius: 20px;
    padding: 32px 36px;
    margin-bottom: 1.4rem;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-lg);
}
.hero-banner::after {
    content: '';
    position: absolute;
    top: -50%; right: -20%;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(45,106,79,0.15) 0%, transparent 70%);
    pointer-events: none;
}
.hero-title {
    font-family: 'Inter', sans-serif;
    font-weight: 900;
    font-size: 1.5rem;
    color: #FFFFFF;
    letter-spacing: -0.03em;
    line-height: 1.2;
    margin-bottom: 4px;
}
.hero-sub {
    font-size: 0.78rem;
    color: rgba(255,255,255,0.6);
    letter-spacing: 0.02em;
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────── Sidebar — Réglages ─────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
        <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#2D6A4F,#3A8F71);display:flex;align-items:center;justify-content:center;font-weight:900;font-size:1.1rem;color:#FFFFFF;font-family:'Inter',sans-serif;">G</div>
        <div>
            <div style="font-family:'Inter',sans-serif;font-weight:800;font-size:1.05rem;color:#FFFFFF;line-height:1.2;">Gravel Coach</div>
            <div style="font-size:0.62rem;color:#8899AA;letter-spacing:0.06em;text-transform:uppercase;font-weight:600;">Performance · Indoor & Outdoor</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("")  # spacer

    st.markdown("### Profil")
    ftp = st.number_input("FTP (watts)", 100, 500, int(st.session_state.get("ftp", 250)), step=5, key="ftp_input")
    st.session_state["ftp"] = ftp
    weight_kg = st.number_input("Poids (kg)", 40.0, 150.0, float(st.session_state.get("weight_kg", 75.0)), step=0.5, key="weight_input")
    st.session_state["weight_kg"] = weight_kg

    st.markdown("### Objectifs Z2")
    z2_goal = st.number_input("Objectif Z2 (W)", 100, 400, int(st.session_state.get("z2_goal", 260)), step=5)
    st.session_state["z2_goal"] = z2_goal
    z2_baseline = st.number_input("Baseline Z2 (W)", 100, 400, int(st.session_state.get("z2_baseline", 220)), step=5)
    st.session_state["z2_baseline"] = z2_baseline

    st.markdown("### Synchronisation Garmin")

    # ── Garmin MFA flow ──
    if "garmin_client" not in st.session_state:
        st.session_state["garmin_client"] = None
    if "garmin_state" not in st.session_state:
        st.session_state["garmin_state"] = None
    if "garmin_needs_mfa" not in st.session_state:
        st.session_state["garmin_needs_mfa"] = False

    if st.session_state["garmin_needs_mfa"]:
        mfa_code = st.text_input("Code MFA (email/SMS)", key="mfa_code_input")
        col_mfa1, col_mfa2 = st.columns(2)
        with col_mfa1:
            if st.button("✓ Valider MFA", use_container_width=True):
                if mfa_code:
                    try:
                        client = login_step2_mfa(
                            st.session_state["garmin_client"],
                            st.session_state["garmin_state"],
                            mfa_code.strip(),
                        )
                        n = sync_recent(client=client, ftp=ftp, weight_kg=weight_kg)
                        st.session_state["garmin_needs_mfa"] = False
                        st.success(f"✅ {n} activités synchronisées")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        with col_mfa2:
            if st.button("✕ Annuler", use_container_width=True):
                st.session_state["garmin_needs_mfa"] = False
                st.rerun()
    else:
        days_back = st.selectbox("Période", [30, 90, 180, 365, 730], index=3,
                                 format_func=lambda d: f"{d} jours")
        if st.button("🔄 Synchroniser Garmin", use_container_width=True):
            with st.spinner("Connexion à Garmin Connect..."):
                try:
                    status, client, state = login_step1()
                    if status == "needs_mfa":
                        st.session_state["garmin_needs_mfa"] = True
                        st.session_state["garmin_client"] = client
                        st.session_state["garmin_state"] = state
                        st.info("📱 Un code MFA a été envoyé — saisis-le ci-dessus.")
                        st.rerun()
                    else:
                        n = sync_recent(days_back=days_back, ftp=ftp, client=client, weight_kg=weight_kg)
                        st.success(f"✅ {n} activités synchronisées")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

    # ── Strava (optionnel) ──
    with st.expander("Strava (optionnel)"):
        if st.session_state.get("strava_just_connected"):
            st.success("✅ Strava connecté !")
            st.session_state["strava_just_connected"] = False

        if strava_sync.is_connected():
            st.success("Strava connecté")
            if st.button("Sync Strava", use_container_width=True):
                token = strava_sync.get_valid_token()
                if token:
                    n = sync_strava(token, ftp=ftp, weight_kg=weight_kg)
                    st.success(f"{n} activités Strava synchronisées")
                    st.rerun()
            if st.button("Déconnecter Strava", use_container_width=True):
                strava_sync.disconnect()
                st.rerun()
        else:
            st.info("Strava nécessite un abonnement payant pour l'accès API depuis juin 2026.")

    # ── Import de fichier FIT/GPX/TCX ──
    st.markdown("### Import de fichier")
    uploaded_file = st.file_uploader(
        "Importer un fichier d'activité",
        type=["fit", "gpx", "tcx"],
        help="Formats supportés : FIT, GPX, TCX",
        key="file_uploader",
    )
    if uploaded_file is not None:
        import hashlib
        file_bytes = uploaded_file.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        conn = db.get_conn()
        if db.file_already_imported(conn, file_hash):
            st.info("Ce fichier a déjà été importé.")
        else:
            ride_df = parse_file(uploaded_file.name, file_bytes)
            if ride_df.empty:
                st.error("Impossible de lire ce fichier ou aucune donnée exploitable.")
            else:
                st.session_state["imported_ride_df"] = ride_df
                st.session_state["imported_ride_filename"] = uploaded_file.name
                st.session_state["imported_ride_hash"] = file_hash
                # Sauvegarder l'activité en base
                from analysis import normalized_power as _np_calc, training_stress_score as _tss_calc
                from analysis import best_efforts as _best_efforts, difficulty_score as _diff_score
                from analysis import intensity_factor as _if_calc, time_and_avg_power_per_zone as _zone_calc
                summary = extract_summary_from_df(ride_df, uploaded_file.name)
                if summary:
                    act_id = db.next_activity_id(conn)
                    summary["activity_id"] = act_id
                    summary["source"] = "file_import"
                    summary["category"] = db.detect_category(summary)
                    # Métriques avancées
                    if ride_df["power_w"].notna().any():
                        np_w = _np_calc(ride_df)
                        summary["normalized_power_w"] = np_w
                        summary["intensity_factor"] = _if_calc(np_w, ftp)
                        summary["tss"] = _tss_calc(np_w, ftp, summary.get("duration_s") or 0)
                        efforts = _best_efforts(ride_df)
                        summary["best_5s_w"] = efforts.get(5)
                        summary["best_1m_w"] = efforts.get(60)
                        summary["best_5m_w"] = efforts.get(300)
                        summary["best_20m_w"] = efforts.get(1200)
                        summary["best_60m_w"] = efforts.get(3600)
                    if "cadence" in ride_df and ride_df["cadence"].notna().any():
                        summary["cadence_avg"] = float(ride_df["cadence"].mean())
                        summary["cadence_max"] = float(ride_df["cadence"].max())
                    summary["difficulty_score"] = _diff_score(
                        summary.get("distance_m"), summary.get("elevation_gain_m"),
                        summary.get("duration_s"), summary.get("avg_power_w"), ftp,
                    )
                    if weight_kg > 0 and summary.get("avg_power_w"):
                        summary["watts_per_kg"] = round(summary["avg_power_w"] / weight_kg, 2)
                    db.upsert_activity(conn, summary)
                    file_fmt = uploaded_file.name.rsplit(".", 1)[-1].upper()
                    db.save_ride_file(conn, act_id, uploaded_file.name, file_fmt, file_hash)
                    st.success(f"✅ Activité importée — va dans l'onglet « Analyse de sortie »")
        conn.close()

    st.markdown("---")
    st.caption("v6.0 · Gravel Coach — Clean White")

# ───────────────────────── Load data ─────────────────────────
df = db.load_activities_df()

if df.empty:
    st.markdown("""
    <div style="text-align:center;padding:80px 20px;">
        <div style="width:72px;height:72px;border-radius:18px;background:linear-gradient(135deg,#2D6A4F,#3A8F71);display:inline-flex;align-items:center;justify-content:center;font-weight:900;font-size:2rem;color:#FFFFFF;font-family:'Inter',sans-serif;margin-bottom:20px;box-shadow:0 8px 24px rgba(45,106,79,0.2);">G</div>
        <h2 style="font-family:'Inter',sans-serif;font-weight:900;color:var(--text-primary);margin:0 0 8px;letter-spacing:-0.02em;">Bienvenue sur Gravel Coach</h2>
        <p style="color:var(--text-muted);font-size:0.9rem;max-width:400px;margin:0 auto;">Synchronise tes données Garmin Connect ou importe un fichier FIT/GPX/TCX via la barre latérale pour commencer.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Ensure category column exists (backward compat)
if "category" not in df.columns:
    df["category"] = df.apply(lambda r: db.detect_category(r.to_dict()), axis=1)
if "watts_per_kg" not in df.columns:
    if weight_kg > 0:
        df["watts_per_kg"] = df["avg_power_w"].apply(lambda p: round(p / weight_kg, 2) if pd.notna(p) else None)
    else:
        df["watts_per_kg"] = None

df["distance_km"] = df["distance_m"] / 1000
df["duration_h"] = df["duration_s"] / 3600
df["date"] = df["start_time"].dt.date
df["week"] = df["start_time"].dt.isocalendar().week.astype(int)
df["month"] = df["start_time"].dt.to_period("M").astype(str)

# Split
df_outdoor = df[df["category"] == "outdoor"]
df_indoor = df[df["category"].isin(["indoor", "indoor_zwift"])]
df_zwift = df[df["category"] == "indoor_zwift"]

n_total = len(df)
n_outdoor = len(df_outdoor)
n_indoor = len(df_indoor)
n_zwift = len(df_zwift)

# ───────────────────────── Plotly theme — Clean White ─────────────────────────
PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#4A5568", size=12),
    margin=dict(l=40, r=20, t=30, b=40),
    hoverlabel=dict(bgcolor="#1B2432", bordercolor="#2D3B4E", font_size=12,
                    font_family="Inter", font_color="#FFFFFF"),
)
_GRID = "rgba(0,0,0,0.06)"
_LEGEND = dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#94A3B8"))


def plotly_layout(**overrides):
    """Build a Plotly layout dict merging base style with overrides."""
    layout = dict(**PLOTLY_BASE)
    layout.setdefault("xaxis", dict(gridcolor=_GRID, zerolinecolor=_GRID))
    layout.setdefault("yaxis", dict(gridcolor=_GRID, zerolinecolor=_GRID))
    layout.setdefault("legend", dict(**_LEGEND))
    layout.update(overrides)
    return layout

# Palette Clean White
COL_OUTDOOR = "#2D6A4F"   # forest green
COL_INDOOR = "#E8914F"    # warm orange
COL_ZWIFT = "#5B9BD5"     # soft blue
COL_ACCENT = "#D4783A"    # amber

# ───────────────────────── KPI row ─────────────────────────
total_dist = df["distance_km"].sum()
total_elev = df["elevation_gain_m"].sum()
total_time = df["duration_h"].sum()
avg_power = df["avg_power_w"].mean() if df["avg_power_w"].notna().any() else 0
avg_wpkg = df["watts_per_kg"].mean() if "watts_per_kg" in df and df["watts_per_kg"].notna().any() else 0

# ── Hero banner ──
_today_str = dt.date.today().strftime("%A %d %B %Y").capitalize()
st.markdown(f"""
<div class="hero-banner">
    <div class="section-kicker" style="color:rgba(255,255,255,0.5);">{_today_str}</div>
    <div class="hero-title">Tableau de bord</div>
    <div class="hero-sub">{n_total} sorties · {total_dist:,.0f} km · {total_elev:,.0f} m D+</div>
</div>
""", unsafe_allow_html=True)

kpi_html = f"""
<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-label">Sorties</div>
    <div class="kpi-value">{n_total}</div>
    <div class="kpi-sub">
      <span class="cat-badge cat-outdoor">{n_outdoor} ext</span>
      <span class="cat-badge cat-indoor">{n_indoor} int</span>
    </div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Distance</div>
    <div class="kpi-value">{total_dist:,.0f} <small>km</small></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Dénivelé</div>
    <div class="kpi-value">{total_elev:,.0f} <small>m</small></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Temps total</div>
    <div class="kpi-value">{total_time:,.0f} <small>h</small></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Puissance moy.</div>
    <div class="kpi-value">{avg_power:.0f} <small>W</small></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">W/kg moyen</div>
    <div class="kpi-value">{avg_wpkg:.2f}</div>
    <div class="kpi-sub">à {weight_kg:.0f} kg</div>
  </div>
</div>
"""
st.markdown(kpi_html, unsafe_allow_html=True)

# ───────────────────────── Main tabs ─────────────────────────
tab_perf, tab_indoor, tab_compare, tab_rides, tab_ride_detail, tab_plan, tab_coach = st.tabs([
    "Performance", "Indoor", "Comparaison",
    "Activités", "Analyse", "Plan", "Coach IA"
])

# ═══════════════════════════ TAB 1 — Performance ═══════════════════════════
with tab_perf:
    st.markdown('<div class="section-header">Charge d\'entraînement — CTL / ATL / TSB</div>', unsafe_allow_html=True)

    tss_data = df.dropna(subset=["tss"])
    if not tss_data.empty:
        daily_tss = tss_data.set_index(tss_data["start_time"].dt.normalize())["tss"].groupby(level=0).sum()
        if len(daily_tss) >= 2:
            pmc = performance_management_chart(daily_tss)
            fig_pmc = go.Figure()
            fig_pmc.add_trace(go.Scatter(x=pmc["date"], y=pmc["ctl"], name="CTL (Fitness)",
                                         line=dict(color=COL_OUTDOOR, width=2.5)))
            fig_pmc.add_trace(go.Scatter(x=pmc["date"], y=pmc["atl"], name="ATL (Fatigue)",
                                         line=dict(color=COL_INDOOR, width=2)))
            fig_pmc.add_trace(go.Scatter(x=pmc["date"], y=pmc["tsb"], name="TSB (Forme)",
                                         line=dict(color=COL_ACCENT, width=2), fill="tozeroy",
                                         fillcolor="rgba(212,120,58,0.10)"))
            fig_pmc.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.12)")
            fig_pmc.update_layout(**plotly_layout(height=340, legend=dict(orientation="h", y=1.12, bgcolor="rgba(0,0,0,0)")))
            st.plotly_chart(fig_pmc, use_container_width=True)
        else:
            st.info("Pas assez de données TSS pour le graphique PMC.")
    else:
        st.info("Aucune donnée de TSS — synchronise des activités avec capteur de puissance.")

    # ── Z2 progress ──
    st.markdown('<div class="section-header">Progression Zone 2</div>', unsafe_allow_html=True)
    z2 = z2_progress(df, goal_w=z2_goal, baseline_w=z2_baseline)
    if z2["current"] is not None:
        col_z2a, col_z2b = st.columns([2, 1])
        with col_z2a:
            z2_rides = df.dropna(subset=["avg_z2_power_w"]).copy()
            if not z2_rides.empty:
                fig_z2 = go.Figure()
                fig_z2.add_trace(go.Scatter(
                    x=z2_rides["start_time"], y=z2_rides["avg_z2_power_w"],
                    mode="markers+lines", name="Z2 avg",
                    marker=dict(size=7, color=COL_OUTDOOR),
                    line=dict(color=COL_OUTDOOR, width=1.5),
                ))
                fig_z2.add_hline(y=z2_goal, line_dash="dash", line_color=COL_ACCENT,
                                 annotation_text=f"Objectif {z2_goal}W")
                fig_z2.add_hline(y=z2_baseline, line_dash="dot", line_color="rgba(0,0,0,0.2)",
                                 annotation_text=f"Baseline {z2_baseline}W")
                fig_z2.update_layout(**plotly_layout(height=260))
                st.plotly_chart(fig_z2, use_container_width=True)
        with col_z2b:
            pct = z2["pct_to_goal"] or 0
            st.metric("Z2 actuelle", f"{z2['current']:.0f} W", f"{pct*100:.0f}% de l'objectif")
    else:
        st.info("Pas de données Z2 — nécessite un capteur de puissance.")

    # ── Power curve ──
    st.markdown('<div class="section-header">Courbe de puissance (best-of)</div>', unsafe_allow_html=True)
    pc_df = db.load_best_power_curve()
    if not pc_df.empty:
        fig_pc = go.Figure()
        fig_pc.add_trace(go.Scatter(
            x=pc_df["duration_s"], y=pc_df["power_w"],
            mode="lines", name="Best power",
            line=dict(color=COL_ACCENT, width=2.5),
            fill="tozeroy", fillcolor="rgba(212,120,58,0.10)",
        ))
        fig_pc.update_xaxes(type="log", title="Durée (s)",
                            tickvals=[5, 10, 30, 60, 300, 600, 1200, 3600],
                            ticktext=["5s", "10s", "30s", "1m", "5m", "10m", "20m", "1h"])
        fig_pc.update_yaxes(title="Watts")
        fig_pc.update_layout(**plotly_layout(height=300))
        st.plotly_chart(fig_pc, use_container_width=True)

    # ── Weekly volume ──
    st.markdown('<div class="section-header">Volume hebdomadaire</div>', unsafe_allow_html=True)
    df["week_start"] = df["start_time"].dt.to_period("W").apply(lambda p: p.start_time)
    weekly = df.groupby(["week_start", "category"]).agg(
        hours=("duration_h", "sum"),
        km=("distance_km", "sum"),
        rides=("activity_id", "count"),
    ).reset_index()

    fig_vol = go.Figure()
    for cat, color, label in [("outdoor", COL_OUTDOOR, "Outdoor"), ("indoor", COL_INDOOR, "Indoor"),
                                ("indoor_zwift", COL_ZWIFT, "Zwift")]:
        subset = weekly[weekly["category"] == cat]
        if not subset.empty:
            fig_vol.add_trace(go.Bar(x=subset["week_start"], y=subset["hours"],
                                     name=label, marker_color=color))
    fig_vol.update_layout(**plotly_layout(barmode="stack", height=280,
                          legend=dict(orientation="h", y=1.12),
                          yaxis_title="Heures"))
    st.plotly_chart(fig_vol, use_container_width=True)


# ═══════════════════════════ TAB 2 — Indoor / Zwift ═══════════════════════════
with tab_indoor:
    if df_indoor.empty:
        st.info("Aucune activité indoor/Zwift détectée. Les sorties Zwift synchronisées via Garmin Connect "
                "apparaîtront automatiquement ici.")
    else:
        # KPI indoor
        indoor_avg_power = df_indoor["avg_power_w"].mean() if df_indoor["avg_power_w"].notna().any() else 0
        indoor_avg_wpkg = df_indoor["watts_per_kg"].mean() if df_indoor["watts_per_kg"].notna().any() else 0
        indoor_total_h = df_indoor["duration_h"].sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sessions indoor", f"{n_indoor}")
        c2.metric("Dont Zwift", f"{n_zwift}")
        c3.metric("W/kg moyen", f"{indoor_avg_wpkg:.2f}")
        c4.metric("Heures indoor", f"{indoor_total_h:.0f}h")

        # ── W/kg evolution ──
        st.markdown('<div class="section-header">Évolution W/kg — Sessions indoor</div>', unsafe_allow_html=True)
        indoor_power = df_indoor.dropna(subset=["watts_per_kg"]).copy()
        if not indoor_power.empty:
            fig_wpkg = go.Figure()
            # Separate Zwift vs other indoor
            zwift_mask = indoor_power["category"] == "indoor_zwift"
            if zwift_mask.any():
                zw = indoor_power[zwift_mask]
                fig_wpkg.add_trace(go.Scatter(
                    x=zw["start_time"], y=zw["watts_per_kg"],
                    mode="markers", name="Zwift",
                    marker=dict(size=9, color=COL_ZWIFT, symbol="diamond"),
                ))
            other = indoor_power[~zwift_mask]
            if not other.empty:
                fig_wpkg.add_trace(go.Scatter(
                    x=other["start_time"], y=other["watts_per_kg"],
                    mode="markers", name="Indoor (HT)",
                    marker=dict(size=8, color=COL_INDOOR),
                ))
            # Trend line
            if len(indoor_power) >= 3:
                rolling = indoor_power.set_index("start_time")["watts_per_kg"].rolling("14D", min_periods=2).mean()
                fig_wpkg.add_trace(go.Scatter(
                    x=rolling.index, y=rolling.values,
                    mode="lines", name="Tendance (14j)",
                    line=dict(color=COL_ACCENT, width=2, dash="dot"),
                ))
            fig_wpkg.update_layout(**plotly_layout(height=300, yaxis_title="W/kg"))
            st.plotly_chart(fig_wpkg, use_container_width=True)
        else:
            st.info("Pas de données de puissance pour les sessions indoor.")

        # ── Indoor power distribution ──
        st.markdown('<div class="section-header">Distribution de puissance indoor</div>', unsafe_allow_html=True)
        indoor_with_power = df_indoor.dropna(subset=["avg_power_w"])
        if not indoor_with_power.empty:
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=indoor_with_power["avg_power_w"],
                nbinsx=20, name="Sessions",
                marker_color=COL_ZWIFT,
                opacity=0.8,
            ))
            fig_dist.add_vline(x=ftp, line_dash="dash", line_color=COL_ACCENT,
                               annotation_text=f"FTP ({ftp}W)")
            fig_dist.update_layout(**plotly_layout(height=250,
                                   xaxis_title="Puissance moyenne (W)", yaxis_title="Nombre"))
            st.plotly_chart(fig_dist, use_container_width=True)

        # ── Recent indoor rides table ──
        st.markdown('<div class="section-header">Dernières sessions indoor</div>', unsafe_allow_html=True)
        cols_show = ["start_time", "name", "category", "duration_h", "avg_power_w", "watts_per_kg",
                     "normalized_power_w", "avg_hr", "tss"]
        avail_cols = [c for c in cols_show if c in df_indoor.columns]
        display_indoor = df_indoor[avail_cols].sort_values("start_time", ascending=False).head(20).copy()
        display_indoor["start_time"] = display_indoor["start_time"].dt.strftime("%d/%m/%Y %H:%M")
        display_indoor["duration_h"] = display_indoor["duration_h"].apply(lambda x: f"{x:.1f}h" if pd.notna(x) else "")
        rename_map = {
            "start_time": "Date", "name": "Nom", "category": "Type",
            "duration_h": "Durée", "avg_power_w": "Moy W", "watts_per_kg": "W/kg",
            "normalized_power_w": "NP", "avg_hr": "FC moy", "tss": "TSS",
        }
        display_indoor.rename(columns={k: v for k, v in rename_map.items() if k in display_indoor.columns}, inplace=True)
        st.dataframe(display_indoor, use_container_width=True, hide_index=True)


# ═══════════════════════════ TAB 3 — Indoor vs Outdoor ═══════════════════════════
with tab_compare:
    if df_indoor.empty or df_outdoor.empty:
        st.info("Il faut des activités indoor ET outdoor pour la comparaison.")
    else:
        st.markdown('<div class="section-header">Comparaison Indoor vs Outdoor</div>', unsafe_allow_html=True)

        # Side-by-side metrics
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🌿 Outdoor")
            out_pw = df_outdoor["avg_power_w"].mean() if df_outdoor["avg_power_w"].notna().any() else 0
            out_hr = df_outdoor["avg_hr"].mean() if df_outdoor["avg_hr"].notna().any() else 0
            out_wpkg = df_outdoor["watts_per_kg"].mean() if df_outdoor["watts_per_kg"].notna().any() else 0
            out_spd = df_outdoor["avg_speed_kmh"].mean() if df_outdoor["avg_speed_kmh"].notna().any() else 0
            st.metric("Puissance moy.", f"{out_pw:.0f} W")
            st.metric("W/kg", f"{out_wpkg:.2f}")
            st.metric("FC moyenne", f"{out_hr:.0f} bpm")
            st.metric("Vitesse moy.", f"{out_spd:.1f} km/h")
            st.metric("Sorties", f"{n_outdoor}")

        with c2:
            st.markdown("#### 🏠 Indoor")
            in_pw = df_indoor["avg_power_w"].mean() if df_indoor["avg_power_w"].notna().any() else 0
            in_hr = df_indoor["avg_hr"].mean() if df_indoor["avg_hr"].notna().any() else 0
            in_wpkg = df_indoor["watts_per_kg"].mean() if df_indoor["watts_per_kg"].notna().any() else 0
            in_spd = df_indoor["avg_speed_kmh"].mean() if df_indoor["avg_speed_kmh"].notna().any() else 0
            delta_pw = f"{in_pw - out_pw:+.0f} W" if out_pw else None
            delta_wpkg = f"{in_wpkg - out_wpkg:+.2f}" if out_wpkg else None
            st.metric("Puissance moy.", f"{in_pw:.0f} W", delta_pw)
            st.metric("W/kg", f"{in_wpkg:.2f}", delta_wpkg)
            st.metric("FC moyenne", f"{in_hr:.0f} bpm")
            st.metric("Vitesse moy.", f"{in_spd:.1f} km/h")
            st.metric("Sessions", f"{n_indoor}")

        # ── Monthly comparison chart ──
        st.markdown('<div class="section-header">Puissance moyenne par mois — Indoor vs Outdoor</div>',
                    unsafe_allow_html=True)
        monthly = df.groupby(["month", "category"]).agg(avg_w=("avg_power_w", "mean")).reset_index()
        fig_cmp = go.Figure()
        for cat, color, label in [("outdoor", COL_OUTDOOR, "Outdoor"), ("indoor", COL_INDOOR, "Indoor"),
                                    ("indoor_zwift", COL_ZWIFT, "Zwift")]:
            sub = monthly[monthly["category"] == cat]
            if not sub.empty:
                fig_cmp.add_trace(go.Bar(x=sub["month"], y=sub["avg_w"], name=label, marker_color=color))
        fig_cmp.update_layout(**plotly_layout(barmode="group", height=300,
                              yaxis_title="Puissance moy. (W)"))
        st.plotly_chart(fig_cmp, use_container_width=True)

        # ── Duration split ──
        st.markdown('<div class="section-header">Répartition du temps</div>', unsafe_allow_html=True)
        time_by_cat = df.groupby("category")["duration_h"].sum()
        fig_pie = go.Figure(go.Pie(
            labels=[{"outdoor": "Outdoor", "indoor": "Indoor (HT)", "indoor_zwift": "Zwift"}.get(c, c)
                    for c in time_by_cat.index],
            values=time_by_cat.values,
            marker=dict(colors=[{"outdoor": COL_OUTDOOR, "indoor": COL_INDOOR,
                                 "indoor_zwift": COL_ZWIFT}.get(c, "#888") for c in time_by_cat.index]),
            hole=0.55,
            textinfo="label+percent",
            textfont=dict(size=13),
        ))
        fig_pie.update_layout(**plotly_layout(height=300, showlegend=False))
        st.plotly_chart(fig_pie, use_container_width=True)


# ═══════════════════════════ TAB 4 — Sorties ═══════════════════════════
with tab_rides:
    st.markdown('<div class="section-header">Toutes les sorties</div>', unsafe_allow_html=True)

    # Filters
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        cat_filter = st.multiselect("Catégorie", ["outdoor", "indoor", "indoor_zwift"],
                                     default=["outdoor", "indoor", "indoor_zwift"])
    with fc2:
        search = st.text_input("🔍 Rechercher (nom)", "")
    with fc3:
        sort_col = st.selectbox("Trier par", ["start_time", "distance_km", "avg_power_w", "tss", "duration_h"],
                                format_func=lambda c: {"start_time": "Date", "distance_km": "Distance",
                                                       "avg_power_w": "Puissance", "tss": "TSS",
                                                       "duration_h": "Durée"}.get(c, c))

    filtered = df[df["category"].isin(cat_filter)].copy()
    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]
    filtered = filtered.sort_values(sort_col, ascending=False)

    cols_display = ["start_time", "name", "category", "distance_km", "duration_h",
                    "elevation_gain_m", "avg_power_w", "watts_per_kg", "avg_speed_kmh",
                    "avg_hr", "tss"]
    avail = [c for c in cols_display if c in filtered.columns]
    show_df = filtered[avail].head(100).copy()
    show_df["start_time"] = show_df["start_time"].dt.strftime("%d/%m/%Y %H:%M")
    show_df["distance_km"] = show_df["distance_km"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "")
    show_df["duration_h"] = show_df["duration_h"].apply(lambda x: f"{x:.1f}h" if pd.notna(x) else "")
    show_df["elevation_gain_m"] = show_df["elevation_gain_m"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "")
    rename = {
        "start_time": "Date", "name": "Nom", "category": "Type",
        "distance_km": "Dist (km)", "duration_h": "Durée",
        "elevation_gain_m": "D+ (m)", "avg_power_w": "W moy",
        "watts_per_kg": "W/kg", "avg_speed_kmh": "km/h",
        "avg_hr": "FC", "tss": "TSS",
    }
    show_df.rename(columns={k: v for k, v in rename.items() if k in show_df.columns}, inplace=True)
    st.dataframe(show_df, use_container_width=True, hide_index=True)
    st.caption(f"{len(filtered)} activités — affichage limité à 100")


# ═══════════════════════════ TAB 5 — Analyse de sortie ═══════════════════════════
with tab_ride_detail:
    st.markdown('<div class="section-header">Analyse détaillée d\'une sortie</div>', unsafe_allow_html=True)

    # Source : fichier importé ou sélection d'une activité existante
    ride_source = st.radio(
        "Source de la sortie",
        ["Fichier importé", "Activité synchronisée"],
        horizontal=True,
        key="ride_source",
    )

    if ride_source == "Fichier importé":
        if "imported_ride_df" in st.session_state and st.session_state["imported_ride_df"] is not None:
            ride_df = st.session_state["imported_ride_df"]
            ride_name = st.session_state.get("imported_ride_filename", "Import")
            render_ride_analysis(st, ride_df, ftp, weight_kg, filename=ride_name)
        else:
            st.info("Importe un fichier FIT, GPX ou TCX via la barre latérale pour analyser une sortie.")
    else:
        # Sélectionner parmi les activités synchronisées qui ont un détail disponible
        if not df.empty:
            ride_options = df[["activity_id", "start_time", "name"]].copy()
            ride_options["label"] = ride_options.apply(
                lambda r: f"{r['start_time'].strftime('%d/%m/%Y')} — {r['name']}" if pd.notna(r['name']) else f"{r['start_time'].strftime('%d/%m/%Y')}",
                axis=1,
            )
            ride_options = ride_options.sort_values("start_time", ascending=False).head(50)

            selected_label = st.selectbox("Choisir une activité", ride_options["label"].tolist())
            sel_row = ride_options[ride_options["label"] == selected_label]
            if not sel_row.empty:
                sel_id = int(sel_row.iloc[0]["activity_id"])
                # Pour les activités Garmin synchronisées, on tente de charger le détail
                if sel_id > 0:
                    st.info("L'analyse détaillée seconde-par-seconde n'est disponible que pour les fichiers importés (FIT/GPX/TCX). "
                            "Les activités synchronisées via Garmin/Strava n'ont que les métriques résumées.")
                    # Afficher quand même les métriques résumées
                    act = df[df["activity_id"] == sel_id].iloc[0]
                    kpi_parts = []
                    if pd.notna(act.get("duration_s")):
                        h, rem = divmod(int(act["duration_s"]), 3600)
                        m, s = divmod(rem, 60)
                        dur_fmt = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                        kpi_parts.append(f'<div class="kpi-card"><div class="kpi-label">Durée</div><div class="kpi-value">{dur_fmt}</div></div>')
                    if pd.notna(act.get("distance_km")):
                        kpi_parts.append(f'<div class="kpi-card"><div class="kpi-label">Distance</div><div class="kpi-value">{act["distance_km"]:.1f} <small style="font-size:0.6em">km</small></div></div>')
                    if pd.notna(act.get("avg_power_w")):
                        kpi_parts.append(f'<div class="kpi-card"><div class="kpi-label">Puissance moy.</div><div class="kpi-value">{act["avg_power_w"]:.0f} <small style="font-size:0.6em">W</small></div></div>')
                    if pd.notna(act.get("tss")):
                        kpi_parts.append(f'<div class="kpi-card"><div class="kpi-label">TSS</div><div class="kpi-value">{act["tss"]:.0f}</div></div>')
                    if pd.notna(act.get("avg_hr")):
                        kpi_parts.append(f'<div class="kpi-card"><div class="kpi-label">FC moy.</div><div class="kpi-value">{act["avg_hr"]:.0f} <small style="font-size:0.6em">bpm</small></div></div>')
                    if kpi_parts:
                        st.markdown(f'<div class="kpi-row">{"".join(kpi_parts)}</div>', unsafe_allow_html=True)
                else:
                    # Activité importée par fichier — tenter de recharger depuis session state
                    st.info("Pour les activités importées, ré-importe le fichier via la sidebar pour l'analyse détaillée.")
        else:
            st.info("Aucune activité disponible.")


# ═══════════════════════════ TAB 6 — Plan d'entraînement ═══════════════════════════
with tab_plan:
    st.markdown('<div class="section-header">Plan d\'entraînement structuré</div>', unsafe_allow_html=True)
    st.caption("Plan hebdomadaire adaptatif basé sur tes performances et ta charge actuelle.")

    # ── Training plan storage ──
    if "training_plan" not in st.session_state:
        st.session_state["training_plan"] = None

    def generate_training_plan(df_activities, ftp_val, weight_val):
        """Génère un plan d'entraînement sur 7 jours basé sur l'état de forme actuel."""
        today = dt.date.today()
        plan_days = []

        # Évaluer l'état actuel
        tss_data = df_activities.dropna(subset=["tss"])
        tsb_val = None
        ctl_val = None
        if not tss_data.empty:
            daily = tss_data.set_index(tss_data["start_time"].dt.normalize())["tss"].groupby(level=0).sum()
            if len(daily) >= 2:
                pmc = performance_management_chart(daily)
                if not pmc.empty:
                    ctl_val = float(pmc["ctl"].iloc[-1])
                    tsb_val = float(pmc["tsb"].iloc[-1])

        # Semaine type adaptée au TSB
        if tsb_val is not None and tsb_val < -20:
            # Récupération
            week_template = [
                ("Repos complet", "rest", 0, "Récupération active ou repos"),
                ("Z2 léger", "indoor", 45, f"Endurance facile à {int(ftp_val*0.55)}-{int(ftp_val*0.65)}W"),
                ("Repos", "rest", 0, "Repos ou stretching"),
                ("Z2 modéré", "outdoor", 60, f"Endurance à {int(ftp_val*0.60)}-{int(ftp_val*0.70)}W"),
                ("Z1 récupération", "indoor", 30, "Pédalage léger, jambes légères"),
                ("Z2 sortie", "outdoor", 90, f"Sortie endurance à {int(ftp_val*0.60)}-{int(ftp_val*0.70)}W"),
                ("Repos", "rest", 0, "Repos complet"),
            ]
        elif tsb_val is not None and tsb_val > 10:
            # Frais — bloc intense
            week_template = [
                ("Intervalles Z4/Z5", "indoor", 60,
                 f"Échauffement 15min + 4×4min à {int(ftp_val*0.95)}-{int(ftp_val*1.05)}W (rec 3min) + retour au calme"),
                ("Z2 récupération", "indoor", 45, f"Endurance facile à {int(ftp_val*0.55)}-{int(ftp_val*0.65)}W"),
                ("Sweet Spot", "indoor", 60,
                 f"Échauffement 15min + 2×15min à {int(ftp_val*0.88)}-{int(ftp_val*0.93)}W (rec 5min)"),
                ("Repos", "rest", 0, "Repos ou yoga/stretching"),
                ("Z2 + sprints", "outdoor", 75,
                 f"Z2 avec 6×10s sprints max (récup complète entre chaque)"),
                ("Sortie longue", "outdoor", 150,
                 f"Endurance Z2 ({int(ftp_val*0.60)}-{int(ftp_val*0.75)}W) avec terrain vallonné"),
                ("Repos", "rest", 0, "Repos complet"),
            ]
        else:
            # Standard — construction
            week_template = [
                ("Intervalles Z4", "indoor", 60,
                 f"Échauffement 15min + 3×8min à {int(ftp_val*0.90)}-{int(ftp_val*1.00)}W (rec 4min) + retour au calme"),
                ("Z2 endurance", "outdoor", 75, f"Endurance à {int(ftp_val*0.60)}-{int(ftp_val*0.75)}W"),
                ("Repos", "rest", 0, "Repos ou mobilité"),
                ("Tempo Z3", "indoor", 50,
                 f"Échauffement 10min + 2×12min à {int(ftp_val*0.76)}-{int(ftp_val*0.88)}W (rec 5min)"),
                ("Z2 léger", "indoor", 40, f"Récup active à {int(ftp_val*0.55)}-{int(ftp_val*0.65)}W"),
                ("Sortie longue", "outdoor", 120,
                 f"Endurance Z2 ({int(ftp_val*0.60)}-{int(ftp_val*0.75)}W), cadence 85-95rpm"),
                ("Repos", "rest", 0, "Repos complet"),
            ]

        for i, (title, env, minutes, detail) in enumerate(week_template):
            day_date = today + dt.timedelta(days=i)
            # Check if there's already an activity that day
            done = not df_activities[df_activities["date"] == day_date].empty
            plan_days.append({
                "date": day_date,
                "day_name": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][day_date.weekday()],
                "title": title,
                "environment": env,
                "duration_min": minutes,
                "detail": detail,
                "done": done if i == 0 else False,
            })

        return {
            "generated": today.isoformat(),
            "tsb": tsb_val,
            "ctl": ctl_val,
            "ftp": ftp_val,
            "days": plan_days,
        }

    col_gen, col_info = st.columns([1, 2])
    with col_gen:
        if st.button("🔄 Générer le plan", use_container_width=True):
            st.session_state["training_plan"] = generate_training_plan(df, ftp, weight_kg)
            st.rerun()

    plan = st.session_state.get("training_plan")
    if plan is None:
        st.info("Clique sur « Générer le plan » pour créer un plan d'entraînement "
                "adapté à ton état de forme actuel.")
    else:
        with col_info:
            tsb_txt = f"TSB: {plan['tsb']:+.0f}" if plan["tsb"] is not None else "TSB: N/A"
            ctl_txt = f"CTL: {plan['ctl']:.0f}" if plan["ctl"] is not None else "CTL: N/A"
            if plan["tsb"] is not None:
                if plan["tsb"] < -20:
                    mode = "🟠 Mode récupération"
                elif plan["tsb"] > 10:
                    mode = "🟢 Mode intensif"
                else:
                    mode = "🔵 Mode construction"
            else:
                mode = "🔵 Mode standard"
            st.markdown(f"**{mode}** — {tsb_txt} · {ctl_txt} · FTP {plan['ftp']}W")

        today = dt.date.today()
        for day in plan["days"]:
            d = day["date"]
            if d < today:
                status_class = "done"
                icon = "✅" if day["done"] else "⬜"
            elif d == today:
                status_class = "today"
                icon = "▶️"
            else:
                status_class = "future"
                icon = "📌"

            env_badge = ""
            if day["environment"] == "indoor":
                env_badge = '<span class="cat-badge cat-indoor">Indoor</span>'
            elif day["environment"] == "outdoor":
                env_badge = '<span class="cat-badge cat-outdoor">Outdoor</span>'
            else:
                env_badge = '<span class="cat-badge" style="background:var(--bg-muted);color:var(--text-muted);">Repos</span>'

            dur_txt = f" · {day['duration_min']}min" if day["duration_min"] > 0 else ""

            st.markdown(f"""
            <div class="plan-card {status_class}">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <span style="font-size:0.78rem;color:var(--text-secondary);">{icon} {day['day_name']} {d.strftime('%d/%m')}</span>
                        <span style="margin-left:8px;font-weight:700;color:var(--text-primary);">{day['title']}</span>
                        {dur_txt}
                    </div>
                    <div>{env_badge}</div>
                </div>
                <div style="font-size:0.82rem;color:var(--text-secondary);margin-top:6px;">{day['detail']}</div>
            </div>
            """, unsafe_allow_html=True)

        # Weekly summary
        total_plan_min = sum(d["duration_min"] for d in plan["days"])
        indoor_count = sum(1 for d in plan["days"] if d["environment"] == "indoor")
        outdoor_count = sum(1 for d in plan["days"] if d["environment"] == "outdoor")
        rest_count = sum(1 for d in plan["days"] if d["environment"] == "rest")

        st.markdown(f"""
        <div style="margin-top:16px;padding:14px 18px;background:var(--bg-card);border-radius:var(--radius);border:1px solid var(--border);">
            <span style="font-weight:700;font-family:'Inter',sans-serif;color:var(--text-primary);">Résumé de la semaine</span>
            <span style="color:var(--text-secondary);margin-left:12px;font-family:'JetBrains Mono',monospace;font-size:0.85rem;">
                {total_plan_min // 60}h{total_plan_min % 60:02d} total ·
                {indoor_count} indoor · {outdoor_count} outdoor · {rest_count} repos
            </span>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════ TAB 7 — Coach IA ═══════════════════════════
with tab_coach:
    report = generate_coach_report(df, ftp=ftp, weight_kg=weight_kg)
    if report is None:
        st.info("Pas assez de données pour le rapport Coach IA. Synchronise plus d'activités.")
    else:
        # Score ring
        c_score, c_fitness, c_volume = st.columns(3)
        with c_score:
            st.markdown(f"""
            <div class="score-ring">
                <div class="score-value">{report.overall_score}</div>
                <div class="score-label">Score global</div>
            </div>
            """, unsafe_allow_html=True)
        with c_fitness:
            st.markdown(f"""
            <div class="score-ring">
                <div style="font-size:2rem;">{report.fitness_emoji}</div>
                <div style="font-size:1.1rem;font-weight:700;font-family:'Inter',sans-serif;color:var(--text-primary);">{report.fitness_status}</div>
                <div style="font-size:0.78rem;font-family:'JetBrains Mono',monospace;color:var(--text-muted);margin-top:4px;">
                    CTL {f"{report.ctl:.0f}" if report.ctl is not None and report.ctl == report.ctl else 'N/A'} · ATL {f"{report.atl:.0f}" if report.atl is not None and report.atl == report.atl else 'N/A'} · TSB {f"{report.tsb:+.0f}" if report.tsb is not None and report.tsb == report.tsb else 'N/A'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c_volume:
            st.markdown(f"""
            <div class="score-ring">
                <div style="font-size:1.6rem;font-weight:700;font-family:'Inter',sans-serif;color:var(--text-primary);">{report.weekly_hours_avg:.1f}h</div>
                <div style="font-size:0.78rem;color:var(--text-muted);">/ semaine · {report.rides_per_week_avg:.1f} sorties</div>
                <div style="font-size:0.78rem;font-family:'JetBrains Mono',monospace;color:var(--text-muted);margin-top:2px;">
                    {report.weekly_km_avg:.0f} km · {report.weekly_elevation_avg:.0f} m D+
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"**{report.fitness_detail}**")

        # Trends
        if report.trend_details:
            st.markdown('<div class="section-header">Tendances</div>', unsafe_allow_html=True)
            for t in report.trend_details:
                st.markdown(f"- {t}")

        # Zone distribution
        if report.zone_distribution:
            st.markdown('<div class="section-header">Distribution des zones</div>', unsafe_allow_html=True)
            zone_df = pd.DataFrame([
                {"Zone": k, "Temps (%)": v} for k, v in report.zone_distribution.items()
            ])
            fig_zones = go.Figure(go.Bar(
                x=zone_df["Temps (%)"], y=zone_df["Zone"],
                orientation="h",
                marker_color=["#2D6A4F", "#3A8F71", "#5B9BD5", "#E8914F",
                              "#D4783A", "#7C6FAF", "#94A3B8"][:len(zone_df)],
            ))
            fig_zones.update_layout(**plotly_layout(height=220, xaxis_title="% du temps"))
            st.plotly_chart(fig_zones, use_container_width=True)
            if report.zone_comment:
                st.markdown(report.zone_comment)

        # Recommendations
        st.markdown('<div class="section-header">Recommandations</div>', unsafe_allow_html=True)
        for rec in report.training_recommendations:
            st.markdown(rec)

        # Nutrition
        with st.expander("🍎 Nutrition & Hydratation"):
            adv = report.nutrition_advice
            st.markdown(f"**Catégorie de sortie type : {adv.duration_category}**")
            st.markdown(f"- Glucides : {adv.carbs_per_hour_g[0]}–{adv.carbs_per_hour_g[1]} g/h")
            st.markdown(f"- Eau : {adv.water_per_hour_ml[0]}–{adv.water_per_hour_ml[1]} ml/h")
            st.markdown(f"- Sodium : {adv.electrolytes_mg_sodium_h[0]}–{adv.electrolytes_mg_sodium_h[1]} mg/h")
            st.markdown(f"- **Avant** : {adv.pre_ride_meal}")
            st.markdown(f"- **Après** : {adv.post_ride}")

        # Consistency
        st.markdown('<div class="section-header">Régularité</div>', unsafe_allow_html=True)
        st.progress(report.consistency_score / 100)
        st.caption(report.consistency_comment)
