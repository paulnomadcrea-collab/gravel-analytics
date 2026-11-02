"""
Module d'analyse détaillée d'une sortie vélo.

Fournit les fonctions de visualisation Plotly et le layout Streamlit
pour l'onglet « Analyse de sortie ». Consomme un DataFrame normalisé
(format file_import / parse_power_stream).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis import (
    best_efforts,
    difficulty_score,
    intensity_factor,
    normalized_power,
    time_and_avg_power_per_zone,
    training_stress_score,
)

# ───────────────────────── Couleurs (cohérentes avec streamlit_app) ──────

COL_POWER = "#ea580c"
COL_HR = "#dc2626"
COL_SPEED = "#2563eb"
COL_ALT = "#64748b"
COL_CADENCE = "#0891b2"
COL_ACCENT = "#7c3aed"

_GRID = "rgba(0,0,0,0.06)"
_PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#334155", size=12),
    margin=dict(l=40, r=20, t=30, b=40),
    hoverlabel=dict(bgcolor="#ffffff", bordercolor="#e2e8f0", font_size=12,
                    font_family="Inter", font_color="#0f172a"),
)


def _layout(**kw):
    layout = dict(**_PLOTLY_BASE)
    layout.setdefault("xaxis", dict(gridcolor=_GRID, zerolinecolor=_GRID))
    layout.setdefault("yaxis", dict(gridcolor=_GRID, zerolinecolor=_GRID))
    layout.setdefault("legend", dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#64748b")))
    layout.update(kw)
    return layout


# ───────────────────────── Helpers de formatage ─────────────────────────

def _fmt_duration(seconds: float) -> str:
    """Formate une durée en h:mm:ss ou mm:ss."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _elapsed_to_time_labels(elapsed_s: pd.Series) -> pd.Series:
    """Convertit elapsed_s en labels mm:ss / h:mm:ss pour l'axe X."""
    return elapsed_s.apply(_fmt_duration)


# ───────────────────────── Métriques résumées ───────────────────────────

def compute_ride_metrics(df: pd.DataFrame, ftp: float, weight_kg: float) -> dict:
    """Calcule toutes les métriques clés d'une sortie à partir du DataFrame."""
    metrics = {}

    duration_s = df["elapsed_s"].max() - df["elapsed_s"].min() if not df.empty else 0
    metrics["duration_s"] = duration_s
    metrics["duration_fmt"] = _fmt_duration(duration_s)

    # Distance
    if "speed_kmh" in df and df["speed_kmh"].notna().any():
        dt_s = df["elapsed_s"].diff().fillna(1).clip(lower=0, upper=10)
        metrics["distance_km"] = float((df["speed_kmh"].fillna(0) / 3.6 * dt_s).sum() / 1000)
    else:
        metrics["distance_km"] = None

    # Vitesse
    if df["speed_kmh"].notna().any():
        metrics["avg_speed_kmh"] = float(df["speed_kmh"].mean())
        metrics["max_speed_kmh"] = float(df["speed_kmh"].max())
    else:
        metrics["avg_speed_kmh"] = None
        metrics["max_speed_kmh"] = None

    # Puissance
    has_power = df["power_w"].notna().any()
    if has_power:
        metrics["avg_power_w"] = float(df["power_w"].mean())
        metrics["max_power_w"] = float(df["power_w"].max())
        np_w = normalized_power(df)
        metrics["normalized_power_w"] = np_w
        metrics["intensity_factor"] = intensity_factor(np_w, ftp)
        metrics["tss"] = training_stress_score(np_w, ftp, duration_s)
        if weight_kg > 0:
            metrics["watts_per_kg"] = round(metrics["avg_power_w"] / weight_kg, 2)
            metrics["np_per_kg"] = round(np_w / weight_kg, 2) if np_w == np_w else None
        else:
            metrics["watts_per_kg"] = None
            metrics["np_per_kg"] = None
    else:
        metrics["avg_power_w"] = None
        metrics["max_power_w"] = None
        metrics["normalized_power_w"] = None
        metrics["intensity_factor"] = None
        metrics["tss"] = None
        metrics["watts_per_kg"] = None
        metrics["np_per_kg"] = None

    # FC
    if df["hr"].notna().any():
        metrics["avg_hr"] = float(df["hr"].mean())
        metrics["max_hr"] = float(df["hr"].max())
    else:
        metrics["avg_hr"] = None
        metrics["max_hr"] = None

    # Cadence
    if "cadence" in df and df["cadence"].notna().any():
        metrics["avg_cadence"] = float(df["cadence"].mean())
        metrics["max_cadence"] = float(df["cadence"].max())
    else:
        metrics["avg_cadence"] = None
        metrics["max_cadence"] = None

    # Altitude
    if df["altitude_m"].notna().any():
        alt = df["altitude_m"].dropna()
        diffs = alt.diff().dropna()
        metrics["elevation_gain_m"] = float(diffs[diffs > 0].sum())
        metrics["elevation_loss_m"] = float(abs(diffs[diffs < 0].sum()))
        metrics["alt_min"] = float(alt.min())
        metrics["alt_max"] = float(alt.max())
    else:
        metrics["elevation_gain_m"] = None
        metrics["elevation_loss_m"] = None
        metrics["alt_min"] = None
        metrics["alt_max"] = None

    # Best efforts
    if has_power:
        efforts = best_efforts(df)
        metrics["best_efforts"] = efforts
    else:
        metrics["best_efforts"] = {}

    # Difficulty score
    metrics["difficulty_score"] = difficulty_score(
        distance_m=(metrics["distance_km"] or 0) * 1000,
        elevation_gain_m=metrics["elevation_gain_m"],
        duration_s=duration_s,
        avg_power_w=metrics["avg_power_w"],
        ftp=ftp,
    )

    return metrics


# ───────────────────────── Graphiques ───────────────────────────────────

def fig_time_series(df: pd.DataFrame, ftp: float) -> go.Figure:
    """Graphique multi-axes : puissance, FC, vitesse, altitude vs temps."""
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.3, 0.22, 0.22, 0.26],
        subplot_titles=("Puissance (W)", "Fréquence cardiaque (bpm)",
                        "Vitesse (km/h)", "Altitude (m)"),
    )

    elapsed_min = df["elapsed_s"] / 60

    # Puissance
    if df["power_w"].notna().any():
        fig.add_trace(go.Scatter(
            x=elapsed_min, y=df["power_w"],
            mode="lines", name="Puissance",
            line=dict(color=COL_POWER, width=1),
            fill="tozeroy", fillcolor="rgba(234,88,12,0.10)",
        ), row=1, col=1)
        # Ligne FTP
        fig.add_hline(y=ftp, line_dash="dash", line_color=COL_ACCENT,
                       annotation_text=f"FTP {ftp}W", row=1, col=1)
        # NP rolling 30s
        if len(df) >= 30:
            rolling_30 = df["power_w"].fillna(0).rolling(30, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=elapsed_min, y=rolling_30,
                mode="lines", name="Moy. 30s",
                line=dict(color=COL_ACCENT, width=1.5, dash="dot"),
            ), row=1, col=1)

    # FC
    if df["hr"].notna().any():
        fig.add_trace(go.Scatter(
            x=elapsed_min, y=df["hr"],
            mode="lines", name="FC",
            line=dict(color=COL_HR, width=1.2),
            fill="tozeroy", fillcolor="rgba(220,38,38,0.08)",
        ), row=2, col=1)

    # Vitesse
    if df["speed_kmh"].notna().any():
        fig.add_trace(go.Scatter(
            x=elapsed_min, y=df["speed_kmh"],
            mode="lines", name="Vitesse",
            line=dict(color=COL_SPEED, width=1.2),
        ), row=3, col=1)

    # Altitude
    if df["altitude_m"].notna().any():
        fig.add_trace(go.Scatter(
            x=elapsed_min, y=df["altitude_m"],
            mode="lines", name="Altitude",
            line=dict(color=COL_ALT, width=1),
            fill="tozeroy", fillcolor="rgba(100,116,139,0.12)",
        ), row=4, col=1)

    fig.update_xaxes(title_text="Temps (min)", row=4, col=1, gridcolor=_GRID)
    for i in range(1, 5):
        fig.update_yaxes(gridcolor=_GRID, row=i, col=1)
        fig.update_xaxes(gridcolor=_GRID, row=i, col=1)

    fig.update_layout(
        **_PLOTLY_BASE,
        height=700,
        showlegend=True,
        legend=dict(orientation="h", y=1.06, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color="#64748b")),
    )
    # Annotations de sous-titres : style uniforme
    for ann in fig.layout.annotations:
        ann.font = dict(size=12, color="#64748b", family="Inter, sans-serif")

    return fig


def fig_zone_distribution(df: pd.DataFrame, ftp: float) -> go.Figure | None:
    """Barres horizontales : temps passé dans chaque zone de puissance."""
    if not df["power_w"].notna().any():
        return None

    zdf = time_and_avg_power_per_zone(df, ftp)
    total_s = zdf["time_s"].sum()
    if total_s == 0:
        return None

    zdf["pct"] = zdf["time_s"] / total_s * 100
    zdf["label"] = zdf.apply(
        lambda r: f"{r['zone']}  ({r['pct']:.0f}% · {_fmt_duration(r['time_s'])})", axis=1
    )

    zone_colors = ["#16a34a", "#22c55e", "#ea580c", "#7c3aed",
                   "#dc2626", "#ef4444", "#f87171"]

    fig = go.Figure(go.Bar(
        x=zdf["pct"], y=zdf["label"],
        orientation="h",
        marker_color=zone_colors[:len(zdf)],
        text=zdf["avg_power_w"].apply(lambda v: f"{v:.0f}W" if v == v else ""),
        textposition="auto",
    ))
    fig.update_layout(**_layout(height=250, xaxis_title="% du temps"))
    return fig


def fig_best_efforts(efforts: dict[int, float]) -> go.Figure | None:
    """Bar chart des meilleurs efforts à différentes durées."""
    if not efforts:
        return None

    labels_map = {5: "5s", 30: "30s", 60: "1min", 300: "5min",
                  600: "10min", 1200: "20min", 3600: "60min"}
    valid = {d: w for d, w in efforts.items() if w == w}  # exclure NaN
    if not valid:
        return None

    durations = sorted(valid.keys())
    labels = [labels_map.get(d, f"{d}s") for d in durations]
    values = [valid[d] for d in durations]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=COL_ACCENT,
        text=[f"{v:.0f}W" for v in values],
        textposition="outside",
    ))
    fig.update_layout(**_layout(height=280, yaxis_title="Watts",
                                xaxis_title="Durée"))
    return fig


def fig_cadence(df: pd.DataFrame) -> go.Figure | None:
    """Graphique cadence vs temps."""
    if "cadence" not in df or not df["cadence"].notna().any():
        return None

    elapsed_min = df["elapsed_s"] / 60
    fig = go.Figure(go.Scatter(
        x=elapsed_min, y=df["cadence"],
        mode="lines", name="Cadence",
        line=dict(color=COL_CADENCE, width=1.2),
        fill="tozeroy", fillcolor="rgba(8,145,178,0.10)",
    ))
    fig.update_layout(**_layout(height=220, xaxis_title="Temps (min)",
                                yaxis_title="rpm"))
    return fig


def fig_map(df: pd.DataFrame) -> go.Figure | None:
    """Carte GPS du parcours si lat/lon disponibles."""
    if "lat" not in df or "lon" not in df:
        return None
    gps = df.dropna(subset=["lat", "lon"])
    if len(gps) < 2:
        return None

    fig = go.Figure(go.Scattermap(
        lat=gps["lat"], lon=gps["lon"],
        mode="lines",
        line=dict(width=3, color=COL_ACCENT),
    ))
    fig.update_layout(
        map=dict(
            style="open-street-map",
            center=dict(lat=gps["lat"].mean(), lon=gps["lon"].mean()),
            zoom=11,
        ),
        **_PLOTLY_BASE,
        height=400,
        margin=dict(l=0, r=0, t=0, b=0),
    )
    return fig


# ───────────────────────── Rendu Streamlit ──────────────────────────────

def render_ride_analysis(st_module, df: pd.DataFrame, ftp: float,
                         weight_kg: float, filename: str = "") -> dict:
    """Affiche l'analyse complète d'une sortie dans Streamlit.

    Paramètres :
        st_module : le module streamlit (passé pour éviter l'import circulaire)
        df : DataFrame normalisé (elapsed_s, power_w, hr, speed_kmh, altitude_m, cadence, lat, lon)
        ftp : FTP courante
        weight_kg : poids du cycliste
        filename : nom du fichier d'origine

    Retourne les métriques calculées (dict).
    """
    st = st_module

    if df.empty:
        st.warning("Aucune donnée exploitable dans ce fichier.")
        return {}

    metrics = compute_ride_metrics(df, ftp, weight_kg)

    # ── Header ──
    if filename:
        st.markdown(f'<div class="section-header">📂 {filename}</div>', unsafe_allow_html=True)

    # ── KPI cards ──
    kpi_parts = []
    if metrics["duration_s"]:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Durée</div>
            <div class="kpi-value">{metrics['duration_fmt']}</div>
        </div>""")
    if metrics["distance_km"] is not None:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Distance</div>
            <div class="kpi-value">{metrics['distance_km']:.1f} <small style="font-size:0.6em">km</small></div>
        </div>""")
    if metrics["elevation_gain_m"] is not None:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Dénivelé +</div>
            <div class="kpi-value">{metrics['elevation_gain_m']:.0f} <small style="font-size:0.6em">m</small></div>
        </div>""")
    if metrics["avg_power_w"] is not None:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Puissance moy.</div>
            <div class="kpi-value">{metrics['avg_power_w']:.0f} <small style="font-size:0.6em">W</small></div>
            <div class="kpi-sub">NP {metrics['normalized_power_w']:.0f}W · IF {metrics['intensity_factor']:.2f}</div>
        </div>""")
    if metrics["tss"] is not None and metrics["tss"] == metrics["tss"]:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">TSS</div>
            <div class="kpi-value">{metrics['tss']:.0f}</div>
        </div>""")
    if metrics["avg_hr"] is not None:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">FC moy.</div>
            <div class="kpi-value">{metrics['avg_hr']:.0f} <small style="font-size:0.6em">bpm</small></div>
            <div class="kpi-sub">max {metrics['max_hr']:.0f}</div>
        </div>""")
    if metrics["watts_per_kg"] is not None:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">W/kg</div>
            <div class="kpi-value">{metrics['watts_per_kg']:.2f}</div>
        </div>""")
    if metrics["difficulty_score"] is not None:
        kpi_parts.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Difficulté</div>
            <div class="kpi-value">{metrics['difficulty_score']:.0f} <small style="font-size:0.6em">/100</small></div>
        </div>""")

    if kpi_parts:
        st.markdown(f'<div class="kpi-row">{"".join(kpi_parts)}</div>', unsafe_allow_html=True)

    # ── Carte GPS ──
    map_fig = fig_map(df)
    if map_fig is not None:
        st.markdown('<div class="section-header">🗺️ Parcours GPS</div>', unsafe_allow_html=True)
        st.plotly_chart(map_fig, use_container_width=True)

    # ── Graphiques temporels ──
    st.markdown('<div class="section-header">📈 Données de la sortie</div>', unsafe_allow_html=True)
    st.plotly_chart(fig_time_series(df, ftp), use_container_width=True)

    # ── Zones + Best efforts côte à côte ──
    col_left, col_right = st.columns(2)

    with col_left:
        zone_fig = fig_zone_distribution(df, ftp)
        if zone_fig is not None:
            st.markdown('<div class="section-header">🎯 Zones de puissance</div>', unsafe_allow_html=True)
            st.plotly_chart(zone_fig, use_container_width=True)

    with col_right:
        effort_fig = fig_best_efforts(metrics.get("best_efforts", {}))
        if effort_fig is not None:
            st.markdown('<div class="section-header">🏆 Meilleurs efforts</div>', unsafe_allow_html=True)
            st.plotly_chart(effort_fig, use_container_width=True)

    # ── Cadence ──
    cad_fig = fig_cadence(df)
    if cad_fig is not None:
        st.markdown('<div class="section-header">🔄 Cadence</div>', unsafe_allow_html=True)
        st.plotly_chart(cad_fig, use_container_width=True)

    return metrics
