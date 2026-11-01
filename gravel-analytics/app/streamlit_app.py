"""
Dashboard d'analyse des sorties gravel — données Garmin Connect.

Lancer en local :
    streamlit run app/streamlit_app.py

Déploiement : voir le README (Streamlit Community Cloud recommandé, gratuit).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
from analysis import (
    DEFAULT_ZONES,
    performance_management_chart,
    z2_progress,
    zone_bounds_watts,
)
from coach import generate_coach_report
from sync import sync_recent
from garmin_sync import login_step1, login_step2_mfa

st.set_page_config(page_title="Gravel Analytics", page_icon="🚵", layout="wide")

# ---------------------------------------------------------------- CSS ----
st.markdown("""
<style>
/* -------- Global -------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

section[data-testid="stMainBlockContainer"] {
    max-width: 1100px;
    padding-top: 1rem;
}

/* -------- Hero header -------- */
.hero {
    text-align: center;
    padding: 1.2rem 0 0.6rem;
}
.hero h1 {
    font-family: 'Inter', sans-serif;
    font-size: 1.8rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
}
.hero p {
    color: #6b7280;
    font-size: 0.92rem;
    margin: 0.3rem 0 0;
}

/* -------- KPI cards -------- */
.kpi-row {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    justify-content: center;
    margin: 1rem 0 1.5rem;
}
.kpi-card {
    flex: 1 1 140px;
    max-width: 200px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 0.8rem;
    text-align: center;
    transition: transform 0.15s, box-shadow 0.15s;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #94a3b8;
    margin-bottom: 0.25rem;
}
.kpi-value {
    font-family: 'Inter', sans-serif;
    font-size: 1.55rem;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.15;
}
.kpi-unit {
    font-size: 0.82rem;
    font-weight: 500;
    color: #64748b;
}

/* -------- Section headers -------- */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 1.8rem 0 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #f1f5f9;
}
.section-header .icon {
    font-size: 1.2rem;
}
.section-header h3 {
    font-family: 'Inter', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
}

/* -------- Empty state -------- */
.empty-state {
    text-align: center;
    padding: 2.5rem 1rem;
    background: #f8fafc;
    border-radius: 12px;
    border: 1px dashed #cbd5e1;
    margin: 1rem 0;
}
.empty-state .icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
.empty-state p { color: #64748b; font-size: 0.9rem; max-width: 400px; margin: 0.3rem auto; }

/* -------- Period badge -------- */
.period-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #f1f5f9;
    border-radius: 20px;
    padding: 0.35rem 0.9rem;
    font-size: 0.82rem;
    color: #475569;
    margin: 0.3rem 0 0.8rem;
}

/* -------- Info callout -------- */
.info-callout {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    font-size: 0.85rem;
    color: #92400e;
    margin: 0.5rem 0;
}
.info-callout .ic { font-size: 1.1rem; flex-shrink: 0; margin-top: 0.05rem; }

/* -------- Sidebar polish -------- */
section[data-testid="stSidebar"] {
    background: #fafbfc;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {
    font-size: 1.05rem;
    font-weight: 600;
    color: #334155;
    margin-top: 1rem;
    padding-top: 0.6rem;
    border-top: 1px solid #e2e8f0;
}

/* -------- Tab container -------- */
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-size: 0.88rem;
    font-weight: 500;
    padding: 0.6rem 1rem;
}

/* -------- Plotly charts — thinner frames -------- */
.stPlotlyChart { border-radius: 10px; overflow: hidden; }

/* -------- Mobile responsive -------- */
@media (max-width: 768px) {
    section[data-testid="stMainBlockContainer"] {
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    .hero h1 { font-size: 1.35rem; }
    .kpi-row { gap: 0.5rem; }
    .kpi-card {
        flex: 1 1 calc(50% - 0.5rem);
        max-width: none;
        padding: 0.75rem 0.5rem;
    }
    .kpi-value { font-size: 1.25rem; }
    .kpi-label { font-size: 0.68rem; }
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        font-size: 0.78rem;
        padding: 0.5rem 0.6rem;
    }
    /* Stack columns on mobile */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
}

/* -------- Coach IA — Strava-inspired cards -------- */
.coach-score-ring {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.5rem;
    padding: 1.5rem;
    background: linear-gradient(135deg, #fc4c02 0%, #e8450e 100%);
    border-radius: 16px;
    color: white;
    margin-bottom: 1rem;
}
.coach-score-ring .score-circle {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    border: 4px solid rgba(255,255,255,0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    flex-shrink: 0;
}
.coach-score-ring .score-number {
    font-family: 'Inter', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
}
.coach-score-ring .score-label {
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.9;
}
.coach-score-ring .score-summary {
    font-size: 0.88rem;
    line-height: 1.5;
    opacity: 0.95;
}

.coach-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 1.2rem;
    margin-bottom: 0.75rem;
    transition: box-shadow 0.15s;
}
.coach-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}
.coach-card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.8rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid #f3f4f6;
}
.coach-card-header .icon {
    font-size: 1.3rem;
}
.coach-card-header h4 {
    font-family: 'Inter', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    color: #1f2937;
    margin: 0;
}
.coach-card-body {
    font-size: 0.88rem;
    color: #4b5563;
    line-height: 1.65;
}

.coach-stat-row {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
}
.coach-stat {
    flex: 1 1 120px;
    background: #f9fafb;
    border-radius: 10px;
    padding: 0.8rem 0.7rem;
    text-align: center;
}
.coach-stat .stat-value {
    font-family: 'Inter', sans-serif;
    font-size: 1.2rem;
    font-weight: 700;
    color: #111827;
}
.coach-stat .stat-label {
    font-size: 0.72rem;
    font-weight: 500;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 0.15rem;
}
.coach-stat .stat-unit {
    font-size: 0.78rem;
    font-weight: 500;
    color: #6b7280;
}

.fitness-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 0.9rem;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: 600;
}
.fitness-badge.green { background: #ecfdf5; color: #065f46; }
.fitness-badge.yellow { background: #fffbeb; color: #92400e; }
.fitness-badge.orange { background: #fff7ed; color: #9a3412; }
.fitness-badge.red { background: #fef2f2; color: #991b1b; }

.coach-rec {
    padding: 0.7rem 1rem;
    border-left: 3px solid #fc4c02;
    background: #fff7ed;
    border-radius: 0 10px 10px 0;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
    color: #4b5563;
    line-height: 1.55;
}

.nutrition-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.82rem;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e5e7eb;
}
.nutrition-table th {
    background: #f9fafb;
    padding: 0.6rem 0.7rem;
    text-align: left;
    font-weight: 600;
    color: #374151;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.nutrition-table td {
    padding: 0.55rem 0.7rem;
    border-top: 1px solid #f3f4f6;
    color: #4b5563;
}
.nutrition-table tr:hover td {
    background: #fef7f0;
}

.trend-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
}
.trend-tag.up { background: #ecfdf5; color: #065f46; }
.trend-tag.flat { background: #f3f4f6; color: #6b7280; }
.trend-tag.down { background: #fef2f2; color: #991b1b; }

.coach-section-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #fc4c02;
    margin: 1.2rem 0 0.5rem;
}

/* -------- Dark mode -------- */
@media (prefers-color-scheme: dark) {
    .kpi-card { background: #1e293b; border-color: #334155; }
    .kpi-value { color: #f1f5f9; }
    .kpi-label { color: #94a3b8; }
    .section-header { border-bottom-color: #334155; }
    .section-header h3 { color: #f1f5f9; }
    .hero p { color: #94a3b8; }
    .empty-state { background: #1e293b; border-color: #475569; }
    .empty-state p { color: #94a3b8; }
    .info-callout { background: #422006; border-color: #92400e; color: #fde68a; }
    .period-badge { background: #1e293b; color: #94a3b8; }

    .coach-card { background: #1e293b; border-color: #334155; }
    .coach-card-header { border-bottom-color: #334155; }
    .coach-card-header h4 { color: #f1f5f9; }
    .coach-card-body { color: #d1d5db; }
    .coach-stat { background: #111827; }
    .coach-stat .stat-value { color: #f9fafb; }
    .coach-stat .stat-label { color: #6b7280; }
    .coach-rec { background: #422006; border-left-color: #fc4c02; color: #fde68a; }
    .nutrition-table th { background: #111827; color: #d1d5db; }
    .nutrition-table td { border-top-color: #334155; color: #d1d5db; }
    .nutrition-table tr:hover td { background: #1a1a2e; }
    .nutrition-table { border-color: #334155; }
    .fitness-badge.green { background: #064e3b; color: #6ee7b7; }
    .fitness-badge.yellow { background: #422006; color: #fcd34d; }
    .fitness-badge.orange { background: #431407; color: #fb923c; }
    .fitness-badge.red { background: #450a0a; color: #fca5a5; }
    .trend-tag.up { background: #064e3b; color: #6ee7b7; }
    .trend-tag.flat { background: #1f2937; color: #9ca3af; }
    .trend-tag.down { background: #450a0a; color: #fca5a5; }
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- Layout theme for plotly
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", size=12, color="#64748b"),
    margin=dict(t=30, b=40, l=50, r=20),
    xaxis=dict(gridcolor="#f1f5f9", gridwidth=1),
    yaxis=dict(gridcolor="#f1f5f9", gridwidth=1),
    hoverlabel=dict(bgcolor="#1e293b", font_color="white", font_size=12),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=11)),
)
COLORS = {
    "primary": "#3b82f6",
    "secondary": "#10b981",
    "accent": "#f59e0b",
    "danger": "#ef4444",
    "muted": "#94a3b8",
    "ctl": "#3b82f6",
    "atl": "#f59e0b",
    "tsb": "#10b981",
}

# ---------------------------------------------------------------- Sidebar --
with st.sidebar:
    st.markdown("## ⚙️ Réglages")

    ftp = st.number_input(
        "FTP actuelle (W)", min_value=100, max_value=500, value=260, step=5,
        help="Puissance au seuil fonctionnel — sert de référence pour calculer tes zones.",
    )
    goal_z2 = st.number_input("Objectif Z2 (W)", value=260, step=5,
                               help="Puissance moyenne cible en zone 2")
    baseline_z2 = st.number_input("Niveau de départ Z2 (W)", value=220, step=5,
                                   help="Puissance de départ pour mesurer ta progression")

    st.markdown("## 🔄 Synchronisation")

    days_back = st.slider("Historique (jours)", 30, 730, 365, step=30)

    # ------------------------------------------------------ Sync avec MFA ------
    if "mfa_state" not in st.session_state:
        st.session_state.mfa_state = None
    if "sync_done" not in st.session_state:
        st.session_state.sync_done = False
    if "sync_message" not in st.session_state:
        st.session_state.sync_message = None

    if st.button("🔄 Synchroniser", use_container_width=True, type="primary"):
        st.session_state.sync_done = False
        st.session_state.sync_message = None

        with st.spinner("Connexion à Garmin Connect..."):
            try:
                status, client, client_state = login_step1()
                if status == "needs_mfa":
                    st.session_state.mfa_state = {
                        "client": client,
                        "client_state": client_state,
                    }
                    st.info("🔐 Code de vérification envoyé par email.")
                else:
                    with st.spinner("Récupération des activités..."):
                        n = sync_recent(days_back=days_back, ftp=ftp, client=client)
                    st.session_state.sync_done = True
                    st.session_state.sync_message = ("success", f"✅ {n} activité(s) synchronisée(s).")
            except Exception as e:
                st.session_state.sync_message = ("error", f"Échec : {e}")

    # Formulaire MFA
    if st.session_state.mfa_state is not None:
        with st.form("mfa_form"):
            st.markdown("**🔐 Validation en 2 étapes**")
            mfa_code = st.text_input(
                "Code de vérification",
                placeholder="123456",
                help="Code reçu par email ou SMS de Garmin.",
            )
            submitted = st.form_submit_button("Valider", use_container_width=True)
            if submitted and mfa_code:
                try:
                    client = login_step2_mfa(
                        st.session_state.mfa_state["client"],
                        st.session_state.mfa_state["client_state"],
                        mfa_code.strip(),
                    )
                    st.session_state.mfa_state = None
                    with st.spinner("Récupération des activités..."):
                        n = sync_recent(days_back=days_back, ftp=ftp, client=client)
                    st.session_state.sync_done = True
                    st.session_state.sync_message = ("success", f"✅ {n} activité(s) synchronisée(s).")
                except Exception as e:
                    st.session_state.sync_message = ("error", f"Échec : {e}")
                    if "connexion" in str(e).lower() or "authentication" in str(e).lower():
                        st.session_state.mfa_state = None

    if st.session_state.sync_message:
        msg_type, msg_text = st.session_state.sync_message
        if msg_type == "success":
            st.success(msg_text)
        else:
            st.error(msg_text)

    st.divider()
    st.caption(
        "Identifiants Garmin configurés via variables d'environnement "
        "ou secrets Streamlit — jamais saisis ici."
    )

# ------------------------------------------------------------------- Data --
df = db.load_activities_df()

# Hero header
st.markdown("""
<div class="hero">
    <h1>🚵 Gravel Analytics</h1>
    <p>Tableau de bord de performance — données Garmin Connect</p>
</div>
""", unsafe_allow_html=True)

if df.empty:
    st.markdown("""
    <div class="empty-state">
        <div class="icon">📡</div>
        <p><strong>Aucune activité en base</strong></p>
        <p>Ouvre le menu latéral et clique sur <em>Synchroniser</em> pour importer tes sorties Garmin.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Filtre de période
min_d, max_d = df["start_time"].min().date(), df["start_time"].max().date()
date_range = st.date_input("📅 Période", (min_d, max_d), min_value=min_d, max_value=max_d,
                            label_visibility="collapsed")
if isinstance(date_range, tuple) and len(date_range) == 2:
    d0, d1 = date_range
    df = df[(df["start_time"].dt.date >= d0) & (df["start_time"].dt.date <= d1)]
    st.markdown(
        f'<div class="period-badge">📅 {d0.strftime("%d %b %Y")} → {d1.strftime("%d %b %Y")}</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------- KPIs ----
total_km = df["distance_m"].sum() / 1000
total_elev = df["elevation_gain_m"].sum()
total_hours = df["duration_s"].sum() / 3600
nb_rides = len(df)

st.markdown(f"""
<div class="kpi-row">
    <div class="kpi-card">
        <div class="kpi-label">Sorties</div>
        <div class="kpi-value">{nb_rides}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Distance</div>
        <div class="kpi-value">{total_km:,.0f} <span class="kpi-unit">km</span></div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Dénivelé</div>
        <div class="kpi-value">{total_elev:,.0f} <span class="kpi-unit">m</span></div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Temps</div>
        <div class="kpi-value">{total_hours:,.1f} <span class="kpi-unit">h</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- Tabs ----
tab_perf, tab_speed, tab_rides, tab_coach = st.tabs(["⚡ Performance", "🏔️ Vitesse & dénivelé", "📋 Sorties", "🧠 Coach IA"])

# =============================== TAB 1 : Performance ========================
with tab_perf:
    # ----- Progression Z2 -----
    st.markdown("""
    <div class="section-header">
        <span class="icon">⚡</span>
        <h3>Progression puissance en Zone 2</h3>
    </div>
    """, unsafe_allow_html=True)

    progress = z2_progress(df, goal_w=goal_z2, baseline_w=baseline_z2)
    z2_df = df.dropna(subset=["avg_z2_power_w"])[["start_time", "avg_z2_power_w"]]

    if not z2_df.empty:
        col_chart, col_metric = st.columns([3, 1])
        with col_chart:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=z2_df["start_time"], y=z2_df["avg_z2_power_w"],
                mode="markers+lines", name="P. moy. Z2",
                marker=dict(size=6, color=COLORS["primary"]),
                line=dict(color=COLORS["primary"], width=1.5),
            ))
            if len(z2_df) >= 3:
                z2_sorted = z2_df.sort_values("start_time")
                z2_sorted["roll"] = z2_sorted["avg_z2_power_w"].rolling(5, min_periods=1).mean()
                fig.add_trace(go.Scatter(
                    x=z2_sorted["start_time"], y=z2_sorted["roll"],
                    mode="lines", name="Moy. mobile (5)",
                    line=dict(width=3, color=COLORS["secondary"]),
                ))
            fig.add_hline(y=goal_z2, line_dash="dash", line_color=COLORS["secondary"],
                          annotation_text=f"Objectif {goal_z2}W",
                          annotation_font_color=COLORS["secondary"])
            fig.add_hline(y=baseline_z2, line_dash="dot", line_color=COLORS["muted"],
                          annotation_text=f"Départ {baseline_z2}W",
                          annotation_font_color=COLORS["muted"])
            fig.update_layout(**PLOT_LAYOUT, height=360, yaxis_title="Watts")
            st.plotly_chart(fig, use_container_width=True)

        with col_metric:
            if progress["current"] is not None:
                st.metric(
                    "Moy. 5 dernières sorties",
                    f"{progress['current']:.0f} W",
                    delta=f"{progress['current'] - baseline_z2:+.0f} W",
                )
                if progress["pct_to_goal"] is not None:
                    pct = progress["pct_to_goal"]
                    st.progress(pct, text=f"{pct*100:.0f}% de l'objectif")
            else:
                st.caption("Pas encore assez de données.")
    else:
        st.markdown("""
        <div class="info-callout">
            <span class="ic">💡</span>
            <div>Pas encore de données de puissance Z2. Un capteur de puissance est nécessaire, et la synchro détaillée doit être activée.</div>
        </div>
        """, unsafe_allow_html=True)

    # ----- Charge d'entraînement -----
    st.markdown("""
    <div class="section-header">
        <span class="icon">📊</span>
        <h3>Charge d'entraînement (CTL / ATL / TSB)</h3>
    </div>
    """, unsafe_allow_html=True)

    tss_df = df.dropna(subset=["tss"])
    if not tss_df.empty:
        daily = tss_df.set_index(tss_df["start_time"].dt.normalize())["tss"].groupby(level=0).sum()
        pmc = performance_management_chart(daily)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=pmc["date"], y=pmc["ctl"], name="Forme (CTL)",
            line=dict(color=COLORS["ctl"], width=2.5),
        ))
        fig2.add_trace(go.Scatter(
            x=pmc["date"], y=pmc["atl"], name="Fatigue (ATL)",
            line=dict(color=COLORS["atl"], width=2.5),
        ))
        fig2.add_trace(go.Bar(
            x=pmc["date"], y=pmc["tsb"], name="Forme (TSB)",
            marker_color=COLORS["tsb"], opacity=0.25,
        ))
        fig2.update_layout(**PLOT_LAYOUT, height=360)
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "**CTL** = charge chronique (fitness, 42j) · **ATL** = charge aiguë (fatigue, 7j) · "
            "**TSB** = CTL − ATL (positif = frais, négatif = fatigué)"
        )
    else:
        st.markdown("""
        <div class="info-callout">
            <span class="ic">💡</span>
            <div>Le TSS nécessite des données de puissance détaillées pour être calculé.</div>
        </div>
        """, unsafe_allow_html=True)

    # ----- Courbe de puissance -----
    st.markdown("""
    <div class="section-header">
        <span class="icon">🏆</span>
        <h3>Meilleure courbe de puissance (records personnels)</h3>
    </div>
    """, unsafe_allow_html=True)

    pc = db.load_best_power_curve()
    if not pc.empty:
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(
            x=pc["duration_s"], y=pc["power_w"],
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.08)",
            line=dict(color=COLORS["primary"], width=2.5),
        ))
        # Nice x-axis labels
        tick_vals = [5, 10, 30, 60, 120, 300, 600, 1200, 3600]
        tick_text = ["5s", "10s", "30s", "1min", "2min", "5min", "10min", "20min", "1h"]
        fig5.update_layout(
            **PLOT_LAYOUT, height=360,
            xaxis_type="log", xaxis_title=None, yaxis_title="Watts",
            xaxis=dict(
                tickvals=tick_vals, ticktext=tick_text,
                gridcolor="#f1f5f9", gridwidth=1,
            ),
        )
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.caption("Courbe de puissance pas encore disponible (nécessite la synchro détaillée).")

# =============================== TAB 2 : Vitesse & dénivelé ================
with tab_speed:
    st.markdown("""
    <div class="section-header">
        <span class="icon">💨</span>
        <h3>Vitesse moyenne par sortie</h3>
    </div>
    """, unsafe_allow_html=True)

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=df["start_time"], y=df["avg_speed_kmh"],
        mode="markers+lines", name="Vitesse moy.",
        marker=dict(size=6, color=COLORS["primary"]),
        line=dict(color=COLORS["primary"], width=1.5),
    ))
    # Trend line
    if len(df) >= 5:
        speed_sorted = df.sort_values("start_time").dropna(subset=["avg_speed_kmh"])
        speed_sorted["roll"] = speed_sorted["avg_speed_kmh"].rolling(7, min_periods=1).mean()
        fig3.add_trace(go.Scatter(
            x=speed_sorted["start_time"], y=speed_sorted["roll"],
            mode="lines", name="Tendance (7)",
            line=dict(width=3, color=COLORS["accent"]),
        ))
    fig3.update_layout(**PLOT_LAYOUT, height=360, yaxis_title="km/h")
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("""
    <div class="section-header">
        <span class="icon">⛰️</span>
        <h3>Dénivelé relatif par sortie</h3>
    </div>
    """, unsafe_allow_html=True)

    df_elev = df.copy()
    df_elev["elev_per_km"] = df_elev["elevation_gain_m"] / (df_elev["distance_m"] / 1000)
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=df_elev["start_time"], y=df_elev["elev_per_km"],
        mode="markers+lines", name="D+/km",
        marker=dict(size=6, color=COLORS["secondary"]),
        line=dict(color=COLORS["secondary"], width=1.5),
    ))
    fig4.update_layout(**PLOT_LAYOUT, height=360, yaxis_title="m de D+ / km")
    st.plotly_chart(fig4, use_container_width=True)

# =============================== TAB 3 : Détail sorties =====================
with tab_rides:
    st.markdown("""
    <div class="section-header">
        <span class="icon">📋</span>
        <h3>Détail des sorties</h3>
    </div>
    """, unsafe_allow_html=True)

    # Search / filter
    search = st.text_input("🔍 Rechercher une sortie", placeholder="Ex : Hochstatt, Eguisheim...",
                            label_visibility="collapsed")

    show_cols = [
        "start_time", "name", "distance_m", "duration_s", "elevation_gain_m",
        "avg_speed_kmh", "avg_power_w", "normalized_power_w", "avg_z2_power_w", "tss", "avg_hr",
    ]
    pretty = df[show_cols].copy().sort_values("start_time", ascending=False)
    pretty["distance_m"] = (pretty["distance_m"] / 1000).round(1)
    pretty["duration_s"] = (pretty["duration_s"] / 60).round(0)
    pretty.columns = [
        "Date", "Nom", "Dist. (km)", "Durée (min)", "D+ (m)",
        "Vit. moy", "P. moy (W)", "NP (W)", "P. Z2 (W)", "TSS", "FC",
    ]

    if search:
        pretty = pretty[pretty["Nom"].str.contains(search, case=False, na=False)]

    st.dataframe(
        pretty,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "Date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY"),
            "Dist. (km)": st.column_config.NumberColumn("Dist.", format="%.1f km"),
            "Durée (min)": st.column_config.NumberColumn("Durée", format="%d min"),
            "D+ (m)": st.column_config.NumberColumn("D+", format="%.0f m"),
            "Vit. moy": st.column_config.NumberColumn("Vit.", format="%.1f km/h"),
            "P. moy (W)": st.column_config.NumberColumn("P. moy", format="%.0f W"),
            "NP (W)": st.column_config.NumberColumn("NP", format="%.0f W"),
            "P. Z2 (W)": st.column_config.NumberColumn("P. Z2", format="%.0f W"),
            "TSS": st.column_config.NumberColumn("TSS", format="%.0f"),
            "FC": st.column_config.NumberColumn("FC", format="%d bpm"),
        },
    )
    st.caption(f"{len(pretty)} sortie(s) affichée(s)")

# =============================== TAB 4 : Coach IA =====================
with tab_coach:
    coach_period = st.select_slider(
        "Période d'analyse",
        options=[7, 14, 28, 60, 90],
        value=28,
        format_func=lambda x: f"{x} jours",
    )

    report = generate_coach_report(df, ftp=ftp, period_days=coach_period)

    if report is None:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">🧠</div>
            <p><strong>Pas assez de données</strong></p>
            <p>Le coach a besoin d'au moins quelques sorties sur la période sélectionnée pour générer un rapport.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # ── Score global + résumé (bannière Strava-style) ──
        st.markdown(f"""
        <div class="coach-score-ring">
            <div class="score-circle">
                <div class="score-number">{report.overall_score}</div>
                <div class="score-label">Score</div>
            </div>
            <div class="score-summary">{report.summary}</div>
        </div>
        """, unsafe_allow_html=True)

        # ── 2 colonnes : État de forme + Volume ──
        col_fitness, col_volume = st.columns(2)

        with col_fitness:
            badge_class = "green"
            if report.fitness_emoji == "🟡":
                badge_class = "yellow"
            elif report.fitness_emoji == "🟠":
                badge_class = "orange"
            elif report.fitness_emoji == "🔴":
                badge_class = "red"

            ctl_str = f"{report.ctl:.0f}" if report.ctl else "—"
            atl_str = f"{report.atl:.0f}" if report.atl else "—"
            tsb_str = f"{report.tsb:+.0f}" if report.tsb is not None else "—"

            st.markdown(f"""
            <div class="coach-card">
                <div class="coach-card-header">
                    <span class="icon">💪</span>
                    <h4>État de forme</h4>
                </div>
                <div class="coach-card-body">
                    <div style="margin-bottom: 0.8rem;">
                        <span class="fitness-badge {badge_class}">{report.fitness_emoji} {report.fitness_status}</span>
                    </div>
                    <p style="margin: 0 0 0.8rem;">{report.fitness_detail}</p>
                    <div class="coach-stat-row">
                        <div class="coach-stat">
                            <div class="stat-value">{ctl_str}</div>
                            <div class="stat-label">CTL (fitness)</div>
                        </div>
                        <div class="coach-stat">
                            <div class="stat-value">{atl_str}</div>
                            <div class="stat-label">ATL (fatigue)</div>
                        </div>
                        <div class="coach-stat">
                            <div class="stat-value">{tsb_str}</div>
                            <div class="stat-label">TSB (forme)</div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_volume:
            st.markdown(f"""
            <div class="coach-card">
                <div class="coach-card-header">
                    <span class="icon">📊</span>
                    <h4>Volume & régularité</h4>
                </div>
                <div class="coach-card-body">
                    <div class="coach-stat-row">
                        <div class="coach-stat">
                            <div class="stat-value">{report.weekly_hours_avg:.1f}<span class="stat-unit">h</span></div>
                            <div class="stat-label">Heures / sem.</div>
                        </div>
                        <div class="coach-stat">
                            <div class="stat-value">{report.weekly_km_avg:.0f}<span class="stat-unit">km</span></div>
                            <div class="stat-label">Km / sem.</div>
                        </div>
                        <div class="coach-stat">
                            <div class="stat-value">{report.rides_per_week_avg:.1f}</div>
                            <div class="stat-label">Sorties / sem.</div>
                        </div>
                    </div>
                    <div class="coach-stat-row" style="margin-top: 0.4rem;">
                        <div class="coach-stat">
                            <div class="stat-value">{report.weekly_elevation_avg:.0f}<span class="stat-unit">m</span></div>
                            <div class="stat-label">D+ / sem.</div>
                        </div>
                        <div class="coach-stat">
                            <div class="stat-value">{report.consistency_score}</div>
                            <div class="stat-label">Régularité</div>
                        </div>
                    </div>
                    <p style="margin: 0.6rem 0 0; font-size: 0.82rem; color: #6b7280;">{report.consistency_comment}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Tendances ──
        if report.trend_details:
            def _trend_class(label):
                if "progression" in (label or "").lower() or "↗" in (label or ""):
                    return "up"
                elif "baisse" in (label or "").lower() or "↘" in (label or ""):
                    return "down"
                return "flat"

            trend_tags = ""
            if report.power_trend:
                tc = _trend_class(report.power_trend)
                trend_tags += f'<span class="trend-tag {tc}">⚡ Puissance {report.power_trend}</span> '
            if report.speed_trend:
                tc = _trend_class(report.speed_trend)
                trend_tags += f'<span class="trend-tag {tc}">💨 Vitesse {report.speed_trend}</span> '
            if report.hr_trend:
                tc = _trend_class(report.hr_trend)
                trend_tags += f'<span class="trend-tag {tc}">❤️ FC {report.hr_trend}</span> '

            trend_details_html = ""
            for detail in report.trend_details:
                trend_details_html += f"<p style='margin: 0.3rem 0;'>{detail}</p>"

            st.markdown(f"""
            <div class="coach-card">
                <div class="coach-card-header">
                    <span class="icon">📈</span>
                    <h4>Tendances de performance</h4>
                </div>
                <div class="coach-card-body">
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.8rem;">
                        {trend_tags}
                    </div>
                    {trend_details_html}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Zones de puissance ──
        if report.zone_distribution:
            zone_bars = ""
            zone_colors = {
                "Z1": "#93c5fd", "Z2": "#86efac", "Z3": "#fde047",
                "Z4": "#fdba74", "Z5": "#fca5a5", "Z6": "#f87171", "Z7": "#ef4444"
            }
            for zone_name, pct in sorted(report.zone_distribution.items()):
                z_key = zone_name.split(" ")[0]
                color = zone_colors.get(z_key, "#94a3b8")
                zone_bars += f"""
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem;">
                    <div style="width: 110px; font-size: 0.78rem; font-weight: 500; color: #6b7280; text-align: right;">{zone_name}</div>
                    <div style="flex: 1; background: #f3f4f6; border-radius: 6px; height: 22px; overflow: hidden;">
                        <div style="width: {min(100, pct):.0f}%; height: 100%; background: {color}; border-radius: 6px;
                             display: flex; align-items: center; padding-left: 6px; font-size: 0.72rem; font-weight: 600; color: #1f2937;">
                            {pct:.0f}%
                        </div>
                    </div>
                </div>
                """

            st.markdown(f"""
            <div class="coach-card">
                <div class="coach-card-header">
                    <span class="icon">🎯</span>
                    <h4>Distribution des zones</h4>
                </div>
                <div class="coach-card-body">
                    {zone_bars}
                    <p style="margin: 0.8rem 0 0; font-size: 0.82rem;">{report.zone_comment or ""}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Recommandations d'entraînement ──
        recs_html = ""
        for rec in report.training_recommendations:
            recs_html += f'<div class="coach-rec">{rec}</div>'

        st.markdown(f"""
        <div class="coach-section-label">Recommandations entraînement</div>
        {recs_html}
        """, unsafe_allow_html=True)

        # ── Nutrition & Hydratation ──
        na = report.nutrition_advice
        during_items = "".join(f"<li>{item}</li>" for item in na.during_ride)
        notes_items = "".join(f"<li>{note}</li>" for note in na.notes) if na.notes else ""

        st.markdown(f"""
        <div class="coach-section-label">Nutrition & hydratation</div>
        <div class="coach-card">
            <div class="coach-card-header">
                <span class="icon">🍌</span>
                <h4>Plan nutrition — sorties {na.duration_category}</h4>
            </div>
            <div class="coach-card-body">
                <div class="coach-stat-row">
                    <div class="coach-stat">
                        <div class="stat-value">{na.carbs_per_hour_g[0]}–{na.carbs_per_hour_g[1]}<span class="stat-unit">g/h</span></div>
                        <div class="stat-label">Glucides</div>
                    </div>
                    <div class="coach-stat">
                        <div class="stat-value">{na.water_per_hour_ml[0]}–{na.water_per_hour_ml[1]}<span class="stat-unit">ml/h</span></div>
                        <div class="stat-label">Hydratation</div>
                    </div>
                    <div class="coach-stat">
                        <div class="stat-value">{na.electrolytes_mg_sodium_h[0]}–{na.electrolytes_mg_sodium_h[1]}<span class="stat-unit">mg/h</span></div>
                        <div class="stat-label">Sodium</div>
                    </div>
                </div>

                <div style="margin-top: 1rem;">
                    <p style="margin: 0.3rem 0;"><strong>🍳 Avant :</strong> {na.pre_ride_meal}</p>
                    <p style="margin: 0.6rem 0 0.2rem;"><strong>🚴 Pendant :</strong></p>
                    <ul style="margin: 0.2rem 0 0.6rem; padding-left: 1.2rem;">{during_items}</ul>
                    <p style="margin: 0.3rem 0;"><strong>🥗 Après :</strong> {na.post_ride}</p>
                </div>
                {"<div style='margin-top: 0.8rem; padding: 0.6rem; background: #fffbeb; border-radius: 8px; font-size: 0.82rem;'><strong>💡 Notes :</strong><ul style='margin: 0.2rem 0 0; padding-left: 1.2rem;'>" + notes_items + "</ul></div>" if notes_items else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Tableau nutrition par sortie récente ──
        if report.ride_specific_nutrition:
            rows_html = ""
            for rn in reversed(report.ride_specific_nutrition):
                rows_html += f"""
                <tr>
                    <td>{rn['date']}</td>
                    <td>{rn['name'][:30]}</td>
                    <td>{rn['duration_h']:.1f}h</td>
                    <td>{rn['intensity']}</td>
                    <td><strong>{rn['calories_estimated']:,}</strong> kcal</td>
                    <td>{rn['carbs_needed_g']}g</td>
                    <td>{rn['water_needed_l']}L</td>
                </tr>
                """

            st.markdown(f"""
            <div class="coach-card">
                <div class="coach-card-header">
                    <span class="icon">📋</span>
                    <h4>Besoins nutritionnels — 5 dernières sorties</h4>
                </div>
                <div class="coach-card-body">
                    <table class="nutrition-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Sortie</th>
                                <th>Durée</th>
                                <th>Intensité</th>
                                <th>Calories</th>
                                <th>Glucides</th>
                                <th>Eau</th>
                            </tr>
                        </thead>
                        <tbody>{rows_html}</tbody>
                    </table>
                    <p style="margin: 0.6rem 0 0; font-size: 0.78rem; color: #9ca3af;">
                        Estimations basées sur la durée et la puissance moyenne. Les besoins réels varient
                        selon la température, l'humidité, et ton métabolisme individuel.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.caption(
            f"Rapport généré le {report.generated_at.strftime('%d/%m/%Y à %H:%M')} · "
            f"{report.rides_analyzed} sortie(s) analysée(s) sur {report.period_days} jours"
        )
