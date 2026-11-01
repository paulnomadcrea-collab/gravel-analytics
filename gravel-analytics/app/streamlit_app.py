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
from sync import sync_recent
from garmin_sync import login_step1, login_step2_mfa

st.set_page_config(page_title="Gravel Analytics", page_icon="🚵", layout="wide")

# ---------------------------------------------------------------- Sidebar --
st.sidebar.title("🚵 Gravel Analytics")
st.sidebar.caption("Connecté à Garmin Connect")

ftp = st.sidebar.number_input(
    "FTP actuelle (W)", min_value=100, max_value=500, value=260, step=5,
    help="Puissance au seuil fonctionnel — sert de référence pour calculer tes zones.",
)
goal_z2 = st.sidebar.number_input("Objectif puissance moyenne Z2 (W)", value=260, step=5)
baseline_z2 = st.sidebar.number_input("Niveau de départ Z2 (W)", value=220, step=5)

days_back = st.sidebar.slider("Historique à synchroniser (jours)", 30, 730, 365, step=30)

# ------------------------------------------------------ Sync avec MFA ------
# Initialisation du session_state pour le flux MFA
if "mfa_state" not in st.session_state:
    st.session_state.mfa_state = None  # None = pas en cours, dict = en attente de code
if "sync_done" not in st.session_state:
    st.session_state.sync_done = False
if "sync_message" not in st.session_state:
    st.session_state.sync_message = None

# Bouton de synchronisation
if st.sidebar.button("🔄 Synchroniser avec Garmin Connect", use_container_width=True):
    st.session_state.sync_done = False
    st.session_state.sync_message = None

    with st.spinner("Connexion à Garmin Connect..."):
        try:
            status, client, client_state = login_step1()

            if status == "needs_mfa":
                # MFA requis — sauvegarder l'état pour le formulaire
                st.session_state.mfa_state = {
                    "client": client,
                    "client_state": client_state,
                }
                st.sidebar.info(
                    "🔐 Garmin a envoyé un code de vérification par email. "
                    "Saisis-le ci-dessous."
                )
            else:
                # Connecté sans MFA (tokens valides)
                with st.spinner("Récupération des activités..."):
                    n = sync_recent(days_back=days_back, ftp=ftp, client=client)
                st.session_state.sync_done = True
                st.session_state.sync_message = ("success", f"{n} activité(s) synchronisée(s).")

        except Exception as e:
            st.session_state.sync_message = ("error", f"Échec de synchro : {e}")

# Formulaire MFA (affiché tant que mfa_state est actif)
if st.session_state.mfa_state is not None:
    with st.sidebar.form("mfa_form"):
        st.write("🔐 **Validation en 2 étapes**")
        mfa_code = st.text_input(
            "Code de vérification",
            placeholder="123456",
            help="Code reçu par email ou SMS de Garmin.",
        )
        submitted = st.form_submit_button("Valider le code", use_container_width=True)

        if submitted and mfa_code:
            try:
                client = login_step2_mfa(
                    st.session_state.mfa_state["client"],
                    st.session_state.mfa_state["client_state"],
                    mfa_code.strip(),
                )
                st.session_state.mfa_state = None  # MFA terminé

                with st.spinner("Récupération des activités..."):
                    n = sync_recent(days_back=days_back, ftp=ftp, client=client)
                st.session_state.sync_done = True
                st.session_state.sync_message = ("success", f"{n} activité(s) synchronisée(s).")

            except Exception as e:
                st.session_state.sync_message = ("error", f"Échec : {e}")
                # Garder mfa_state pour permettre une nouvelle tentative
                # sauf si c'est une erreur de login
                if "connexion" in str(e).lower() or "authentication" in str(e).lower():
                    st.session_state.mfa_state = None

# Afficher le message de résultat
if st.session_state.sync_message:
    msg_type, msg_text = st.session_state.sync_message
    if msg_type == "success":
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)

st.sidebar.divider()
st.sidebar.caption(
    "Identifiants Garmin configurés via variables d'environnement "
    "(GARMIN_EMAIL / GARMIN_PASSWORD) ou secrets Streamlit — jamais saisis ici."
)

# ------------------------------------------------------------------- Data --
df = db.load_activities_df()

st.title("Analyse de tes sorties gravel")

if df.empty:
    st.info(
        "Aucune activité en base pour l'instant. Clique sur **Synchroniser avec "
        "Garmin Connect** dans la barre latérale pour importer tes sorties."
    )
    st.stop()

# Filtre de période
min_d, max_d = df["start_time"].min().date(), df["start_time"].max().date()
date_range = st.date_input("Période", (min_d, max_d), min_value=min_d, max_value=max_d)
if isinstance(date_range, tuple) and len(date_range) == 2:
    d0, d1 = date_range
    df = df[(df["start_time"].dt.date >= d0) & (df["start_time"].dt.date <= d1)]

# ---------------------------------------------------------------- KPIs ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sorties", len(df))
c2.metric("Distance totale", f"{df['distance_m'].sum() / 1000:,.0f} km")
c3.metric("Dénivelé total", f"{df['elevation_gain_m'].sum():,.0f} m")
c4.metric("Temps total", f"{df['duration_s'].sum() / 3600:,.1f} h")

st.divider()

# ----------------------------------------------------- Progression Z2 -----
st.subheader("Progression puissance moyenne en Zone 2")
progress = z2_progress(df, goal_w=goal_z2, baseline_w=baseline_z2)

col_chart, col_metric = st.columns([3, 1])
with col_chart:
    z2_df = df.dropna(subset=["avg_z2_power_w"])[["start_time", "avg_z2_power_w"]]
    if not z2_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=z2_df["start_time"], y=z2_df["avg_z2_power_w"], mode="markers+lines", name="Puissance moy. Z2"))
        if len(z2_df) >= 3:
            z2_df = z2_df.sort_values("start_time")
            z2_df["roll"] = z2_df["avg_z2_power_w"].rolling(5, min_periods=1).mean()
            fig.add_trace(go.Scatter(x=z2_df["start_time"], y=z2_df["roll"], mode="lines", name="Moyenne mobile (5 sorties)", line=dict(width=3)))
        fig.add_hline(y=goal_z2, line_dash="dash", line_color="green", annotation_text=f"Objectif {goal_z2}W")
        fig.add_hline(y=baseline_z2, line_dash="dot", line_color="gray", annotation_text=f"Départ {baseline_z2}W")
        fig.update_layout(height=350, margin=dict(t=10, b=10), yaxis_title="Watts", xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(
            "Pas encore de données de puissance détaillées pour calculer la Z2 "
            "(nécessite un capteur de puissance et la synchro avec détails activés)."
        )

with col_metric:
    if progress["current"] is not None:
        st.metric(
            "Moyenne des 5 dernières sorties",
            f"{progress['current']:.0f} W",
            delta=f"{progress['current'] - baseline_z2:+.0f} W vs départ",
        )
        if progress["pct_to_goal"] is not None:
            st.progress(progress["pct_to_goal"], text=f"{progress['pct_to_goal']*100:.0f}% de l'objectif")
    else:
        st.caption("Pas encore assez de données.")

st.divider()

# ------------------------------------------------ Charge d'entraînement ---
st.subheader("Charge d'entraînement (CTL / ATL / TSB)")
tss_df = df.dropna(subset=["tss"])
if not tss_df.empty:
    daily = tss_df.set_index(tss_df["start_time"].dt.normalize())["tss"].groupby(level=0).sum()
    pmc = performance_management_chart(daily)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=pmc["date"], y=pmc["ctl"], name="Forme physique (CTL)", line=dict(color="#1f77b4")))
    fig2.add_trace(go.Scatter(x=pmc["date"], y=pmc["atl"], name="Fatigue (ATL)", line=dict(color="#ff7f0e")))
    fig2.add_trace(go.Bar(x=pmc["date"], y=pmc["tsb"], name="Forme (TSB)", marker_color="#2ca02c", opacity=0.3))
    fig2.update_layout(height=350, margin=dict(t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "CTL = charge chronique (fitness, moy. 42j) · ATL = charge aiguë (fatigue, moy. 7j) · "
        "TSB = CTL − ATL (forme : positif = frais, négatif = fatigué)."
    )
else:
    st.info("TSS non calculable sans données de puissance détaillées pour l'instant.")

st.divider()

# ------------------------------------------------------- Vitesse & dénivelé
st.subheader("Vitesse et dénivelé")
colA, colB = st.columns(2)
with colA:
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=df["start_time"], y=df["avg_speed_kmh"], mode="markers+lines", name="Vitesse moy."))
    fig3.update_layout(height=300, margin=dict(t=10, b=10), yaxis_title="km/h", title="Vitesse moyenne par sortie")
    st.plotly_chart(fig3, use_container_width=True)
with colB:
    df["elev_per_km"] = df["elevation_gain_m"] / (df["distance_m"] / 1000)
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=df["start_time"], y=df["elev_per_km"], mode="markers+lines", name="D+/km"))
    fig4.update_layout(height=300, margin=dict(t=10, b=10), yaxis_title="m de D+ par km", title="Dénivelé relatif par sortie")
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# -------------------------------------------------------- Courbe de puissance
st.subheader("Meilleure courbe de puissance (record personnel par durée)")
pc = db.load_best_power_curve()
if not pc.empty:
    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(x=pc["duration_s"], y=pc["power_w"], mode="lines+markers"))
    fig5.update_layout(
        height=350, margin=dict(t=10, b=10),
        xaxis_type="log", xaxis_title="Durée (s, échelle log)", yaxis_title="Puissance (W)",
    )
    st.plotly_chart(fig5, use_container_width=True)
else:
    st.caption("Courbe de puissance pas encore disponible (nécessite la synchro détaillée).")

st.divider()

# ------------------------------------------------------------- Table -----
st.subheader("Détail des sorties")
show_cols = [
    "start_time", "name", "distance_m", "duration_s", "elevation_gain_m",
    "avg_speed_kmh", "avg_power_w", "normalized_power_w", "avg_z2_power_w", "tss", "avg_hr",
]
pretty = df[show_cols].copy().sort_values("start_time", ascending=False)
pretty["distance_m"] = (pretty["distance_m"] / 1000).round(1)
pretty["duration_s"] = (pretty["duration_s"] / 60).round(0)
pretty.columns = [
    "Date", "Nom", "Distance (km)", "Durée (min)", "D+ (m)",
    "Vit. moy (km/h)", "P. moy (W)", "NP (W)", "P. moy Z2 (W)", "TSS", "FC moy",
]
st.dataframe(pretty, use_container_width=True, hide_index=True)
