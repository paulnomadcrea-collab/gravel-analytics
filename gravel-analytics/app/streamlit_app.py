"""
Gravel Analytics v2 — Dashboard unifié indoor/outdoor/Zwift.

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
from sync import sync_recent, sync_strava
from garmin_sync import login_step1, login_step2_mfa
import strava_sync

st.set_page_config(page_title="Gravel Analytics", page_icon="🚵", layout="wide")

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

# ───────────────────────── CSS ─────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg-primary: #0e1117;
    --bg-card: #1a1d24;
    --bg-card-hover: #22262e;
    --border: #2d3139;
    --text-primary: #e6e9ef;
    --text-secondary: #9ca3b0;
    --accent-blue: #4a9eff;
    --accent-green: #34d399;
    --accent-orange: #f59e0b;
    --accent-red: #ef4444;
    --accent-purple: #a78bfa;
    --accent-cyan: #22d3ee;
}

html, body, [class*="st-"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--bg-card);
    border-right: 1px solid var(--border);
}

section[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-secondary);
    margin: 1.2rem 0 0.5rem;
}

/* KPI cards */
.kpi-row {
    display: flex;
    gap: 12px;
    margin-bottom: 1rem;
    flex-wrap: wrap;
}
.kpi-card {
    flex: 1;
    min-width: 140px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
    transition: border-color 0.2s;
}
.kpi-card:hover { border-color: var(--accent-blue); }
.kpi-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.1;
}
.kpi-sub {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 2px;
}

/* Category badges */
.cat-badge {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 2px 8px;
    border-radius: 999px;
    text-transform: uppercase;
}
.cat-outdoor { background: rgba(52,211,153,0.15); color: #34d399; }
.cat-indoor { background: rgba(245,158,11,0.15); color: #f59e0b; }
.cat-zwift { background: rgba(74,158,255,0.15); color: #4a9eff; }

/* Section header */
.section-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 1.5rem 0 0.8rem;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Hide Streamlit branding */
#MainMenu, footer, header {visibility: hidden;}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: var(--bg-card);
    border-radius: 10px;
    padding: 3px;
    border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.82rem;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    background: var(--accent-blue) !important;
    color: white !important;
}

/* Training plan card */
.plan-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 10px;
}
.plan-card.done { opacity: 0.6; border-left: 3px solid var(--accent-green); }
.plan-card.today { border-left: 3px solid var(--accent-blue); }
.plan-card.future { border-left: 3px solid var(--border); }

/* Plotly overrides */
.js-plotly-plot .plotly .modebar { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────── Sidebar — Réglages ─────────────────────────
with st.sidebar:
    st.markdown("## 🚵 Gravel Analytics")
    st.caption("Dashboard vélo indoor & outdoor")

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

    st.markdown("---")
    st.caption("v2.0 · Indoor/Outdoor/Zwift")

# ───────────────────────── Load data ─────────────────────────
df = db.load_activities_df()

if df.empty:
    st.markdown("## Bienvenue sur Gravel Analytics 🚵")
    st.info("Synchronise tes données Garmin Connect via la barre latérale pour commencer l'analyse.")
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

# ───────────────────────── Plotly theme ─────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#e6e9ef", size=12),
    margin=dict(l=40, r=20, t=30, b=40),
    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    hoverlabel=dict(bgcolor="#1a1d24", font_size=12, font_family="Inter"),
)

COL_OUTDOOR = "#34d399"
COL_INDOOR = "#f59e0b"
COL_ZWIFT = "#4a9eff"
COL_ACCENT = "#a78bfa"

# ───────────────────────── KPI row ─────────────────────────
total_dist = df["distance_km"].sum()
total_elev = df["elevation_gain_m"].sum()
total_time = df["duration_h"].sum()
avg_power = df["avg_power_w"].mean() if df["avg_power_w"].notna().any() else 0
avg_wpkg = df["watts_per_kg"].mean() if "watts_per_kg" in df and df["watts_per_kg"].notna().any() else 0

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
    <div class="kpi-value">{total_dist:,.0f} <small style="font-size:0.6em">km</small></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Dénivelé</div>
    <div class="kpi-value">{total_elev:,.0f} <small style="font-size:0.6em">m</small></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Temps total</div>
    <div class="kpi-value">{total_time:,.0f} <small style="font-size:0.6em">h</small></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Puissance moy.</div>
    <div class="kpi-value">{avg_power:.0f} <small style="font-size:0.6em">W</small></div>
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
tab_perf, tab_indoor, tab_compare, tab_rides, tab_plan, tab_coach = st.tabs([
    "📊 Performance", "🏠 Indoor / Zwift", "⚖️ Indoor vs Outdoor",
    "📋 Sorties", "📅 Plan d'entraînement", "🧠 Coach IA"
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
                                         fillcolor="rgba(167,139,250,0.08)"))
            fig_pmc.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.15)")
            fig_pmc.update_layout(**PLOTLY_LAYOUT, height=340, legend=dict(orientation="h", y=1.12))
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
                fig_z2.add_hline(y=z2_baseline, line_dash="dot", line_color="rgba(255,255,255,0.2)",
                                 annotation_text=f"Baseline {z2_baseline}W")
                fig_z2.update_layout(**PLOTLY_LAYOUT, height=260)
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
            fill="tozeroy", fillcolor="rgba(167,139,250,0.1)",
        ))
        fig_pc.update_xaxes(type="log", title="Durée (s)",
                            tickvals=[5, 10, 30, 60, 300, 600, 1200, 3600],
                            ticktext=["5s", "10s", "30s", "1m", "5m", "10m", "20m", "1h"])
        fig_pc.update_yaxes(title="Watts")
        fig_pc.update_layout(**PLOTLY_LAYOUT, height=300)
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
    fig_vol.update_layout(**PLOTLY_LAYOUT, barmode="stack", height=280,
                          legend=dict(orientation="h", y=1.12),
                          yaxis_title="Heures")
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
            fig_wpkg.update_layout(**PLOTLY_LAYOUT, height=300, yaxis_title="W/kg")
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
            fig_dist.update_layout(**PLOTLY_LAYOUT, height=250,
                                   xaxis_title="Puissance moyenne (W)", yaxis_title="Nombre")
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
        fig_cmp.update_layout(**PLOTLY_LAYOUT, barmode="group", height=300,
                              yaxis_title="Puissance moy. (W)")
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
        fig_pie.update_layout(**PLOTLY_LAYOUT, height=300, showlegend=False)
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


# ═══════════════════════════ TAB 5 — Plan d'entraînement ═══════════════════════════
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
                env_badge = '<span class="cat-badge" style="background:rgba(255,255,255,0.05);color:#9ca3b0;">Repos</span>'

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
        <div style="margin-top:16px;padding:12px 16px;background:var(--bg-card);border-radius:10px;border:1px solid var(--border);">
            <span style="font-weight:700;color:var(--text-primary);">Résumé de la semaine</span>
            <span style="color:var(--text-secondary);margin-left:12px;">
                {total_plan_min // 60}h{total_plan_min % 60:02d} total ·
                {indoor_count} indoor · {outdoor_count} outdoor · {rest_count} repos
            </span>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════ TAB 6 — Coach IA ═══════════════════════════
with tab_coach:
    report = generate_coach_report(df, ftp=ftp, weight_kg=weight_kg)
    if report is None:
        st.info("Pas assez de données pour le rapport Coach IA. Synchronise plus d'activités.")
    else:
        # Score ring
        c_score, c_fitness, c_volume = st.columns(3)
        with c_score:
            st.markdown(f"""
            <div style="text-align:center;padding:20px;">
                <div style="font-size:3.5rem;font-weight:800;color:var(--accent-blue);">{report.overall_score}</div>
                <div style="font-size:0.85rem;color:var(--text-secondary);margin-top:4px;">Score global</div>
            </div>
            """, unsafe_allow_html=True)
        with c_fitness:
            st.markdown(f"""
            <div style="text-align:center;padding:20px;">
                <div style="font-size:2rem;">{report.fitness_emoji}</div>
                <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary);">{report.fitness_status}</div>
                <div style="font-size:0.78rem;color:var(--text-secondary);margin-top:4px;">
                    CTL {report.ctl:.0f if report.ctl else 'N/A'} · ATL {report.atl:.0f if report.atl else 'N/A'} · TSB {report.tsb:+.0f if report.tsb else 'N/A'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c_volume:
            st.markdown(f"""
            <div style="text-align:center;padding:20px;">
                <div style="font-size:1.6rem;font-weight:700;color:var(--text-primary);">{report.weekly_hours_avg:.1f}h</div>
                <div style="font-size:0.78rem;color:var(--text-secondary);">/ semaine · {report.rides_per_week_avg:.1f} sorties</div>
                <div style="font-size:0.78rem;color:var(--text-secondary);margin-top:2px;">
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
                marker_color=[COL_OUTDOOR, COL_OUTDOOR, COL_INDOOR, COL_ACCENT,
                              "#ef4444", "#ef4444", "#ef4444"][:len(zone_df)],
            ))
            fig_zones.update_layout(**PLOTLY_LAYOUT, height=220, xaxis_title="% du temps")
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
