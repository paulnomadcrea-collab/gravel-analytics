"""
Gravel Coach V2 — Performance page.

Power curve, zone distribution, PMC chart, personal records,
W/kg tracking, FTP progression.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis import (
    performance_management_chart,
    zone_bounds_watts,
    DEFAULT_ZONES,
)
from components.theme import C, ZONE_COLORS, CHART_COLORS, apply_plotly_theme
from components.ui import (
    page_header, section_title, stat_card, empty_state,
    fmt_val, fmt_duration,
)
from components.state import get_ftp, get_weight
from components.demo_data import DEMO_POWER_CURVE, DEMO_ZONES, DEMO_LOAD
import db


def render(df: pd.DataFrame):
    ftp = get_ftp()
    weight = get_weight()
    has_data = not df.empty

    page_header("PERFORMANCE", "Analyse de la performance",
                f"FTP {ftp}W · {ftp/weight:.2f} W/kg" if weight > 0 else f"FTP {ftp}W")

    # ── Top stats ──
    if has_data:
        total_km = df["distance_m"].sum() / 1000 if "distance_m" in df.columns else 0
        total_hours = df["duration_s"].sum() / 3600 if "duration_s" in df.columns else 0
        total_elev = df["elevation_gain_m"].sum() if "elevation_gain_m" in df.columns else 0
        ride_count = len(df)
    else:
        total_km, total_hours, total_elev, ride_count = 10600, 580, 78000, 416

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_card("SORTIES TOTALES", ride_count, "")
    with c2:
        stat_card("DISTANCE TOTALE", f"{total_km:.0f}", "km")
    with c3:
        stat_card("HEURES TOTALES", f"{total_hours:.0f}", "h")
    with c4:
        stat_card("DÉNIVELÉ TOTAL", f"{total_elev:.0f}", "m")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Tabs ──
    tab_curve, tab_pmc, tab_zones, tab_records = st.tabs([
        "⚡ Courbe de puissance",
        "📈 Charge (PMC)",
        "🎯 Distribution zones",
        "🏆 Records personnels",
    ])

    with tab_curve:
        _render_power_curve(ftp, weight)

    with tab_pmc:
        _render_pmc(df, has_data)

    with tab_zones:
        _render_zone_distribution(df, ftp, has_data)

    with tab_records:
        _render_records(df, ftp, weight, has_data)


def _render_power_curve(ftp: float, weight: float):
    """Best power curve across all activities."""
    section_title("⚡", "Meilleure puissance soutenue")

    curve_df = db.load_best_power_curve()
    if not curve_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=curve_df["duration_s"], y=curve_df["power_w"],
            mode="lines", line=dict(color=C["primary"], width=2.5),
            fill="tozeroy", fillcolor="rgba(196,135,58,0.1)",
            name="Meilleur W",
            hovertemplate="Durée: %{x}s<br>Puissance: %{y:.0f}W<extra></extra>",
        ))
        # W/kg on secondary axis
        if weight > 0:
            fig.add_trace(go.Scatter(
                x=curve_df["duration_s"], y=curve_df["power_w"] / weight,
                mode="lines", line=dict(color=C["chart2"], width=1.5, dash="dot"),
                name="W/kg", yaxis="y2",
                hovertemplate="Durée: %{x}s<br>%{y:.2f} W/kg<extra></extra>",
            ))
        # FTP line
        fig.add_hline(y=ftp, line_color=C["text_d"], line_width=1, line_dash="dash",
                      annotation_text=f"FTP {ftp}W", annotation_font_color=C["text_d"])

        apply_plotly_theme(fig, height=380)
        fig.update_layout(
            xaxis=dict(type="log", title="Durée (s)",
                       tickvals=[5, 30, 60, 300, 600, 1200, 3600],
                       ticktext=["5s", "30s", "1min", "5min", "10min", "20min", "1h"]),
            yaxis_title="Watts",
            yaxis2=dict(title="W/kg", overlaying="y", side="right",
                        gridcolor="rgba(0,0,0,0)") if weight > 0 else {},
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        # Demo power curve
        durations = sorted(DEMO_POWER_CURVE.keys())
        powers = [DEMO_POWER_CURVE[d] for d in durations]
        labels = {5: "5s", 30: "30s", 60: "1min", 300: "5min", 600: "10min", 1200: "20min", 3600: "1h"}

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=durations, y=powers, mode="lines+markers",
            line=dict(color=C["primary"], width=2.5),
            marker=dict(size=6), name="Meilleur W",
            fill="tozeroy", fillcolor="rgba(196,135,58,0.1)",
        ))
        fig.add_hline(y=ftp, line_color=C["text_d"], line_width=1, line_dash="dash")
        apply_plotly_theme(fig, height=380)
        fig.update_layout(
            xaxis=dict(type="log", title="Durée",
                       tickvals=durations, ticktext=[labels.get(d, f"{d}s") for d in durations]),
            yaxis_title="Watts",
            annotations=[dict(text="Données de démonstration", xref="paper", yref="paper",
                              x=0.5, y=1.05, showarrow=False, font=dict(size=10, color=C["text_d"]))],
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_pmc(df: pd.DataFrame, has_data: bool):
    """Performance Management Chart."""
    section_title("📈", "Gestion de la performance (PMC)")

    if has_data and "tss" in df.columns and "date" in df.columns:
        daily_tss = df.groupby("date")["tss"].sum()
        daily_tss.index = pd.to_datetime(daily_tss.index)
        if len(daily_tss) > 7:
            pmc = performance_management_chart(daily_tss)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pmc["date"], y=pmc["ctl"],
                name="CTL (Fitness)", line=dict(color=C["chart2"], width=2),
                fill="tozeroy", fillcolor="rgba(109,181,109,0.06)",
            ))
            fig.add_trace(go.Scatter(
                x=pmc["date"], y=pmc["atl"],
                name="ATL (Fatigue)", line=dict(color=C["chart5"], width=2),
            ))
            fig.add_trace(go.Scatter(
                x=pmc["date"], y=pmc["tsb"],
                name="TSB (Forme)", line=dict(color=C["chart4"], width=1.5, dash="dot"),
                fill="tozeroy", fillcolor="rgba(91,160,196,0.06)",
            ))
            # TSS bars
            fig.add_trace(go.Bar(
                x=pmc["date"], y=pmc["tss"],
                name="TSS", marker_color="rgba(196,135,58,0.25)",
                yaxis="y2",
            ))
            fig.add_hline(y=0, line_color="rgba(77,69,62,0.6)", line_width=1)

            apply_plotly_theme(fig, height=400)
            fig.update_layout(
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            title="TSS", tickfont=dict(color=C["text_d"])),
                legend=dict(orientation="h", y=1.12),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # Current values
            c1, c2, c3 = st.columns(3)
            with c1:
                stat_card("CTL (FITNESS)", f"{pmc['ctl'].iloc[-1]:.0f}", "")
            with c2:
                stat_card("ATL (FATIGUE)", f"{pmc['atl'].iloc[-1]:.0f}", "")
            with c3:
                tsb_val = pmc['tsb'].iloc[-1]
                label = "Frais" if tsb_val > 5 else ("Forme" if tsb_val > -5 else "Fatigué")
                stat_card("TSB (FORME)", f"{tsb_val:+.0f}", label)
        else:
            st.info("Pas assez de données pour calculer le PMC (minimum 7 jours).")
    else:
        st.info("Synchronisez vos activités pour voir la courbe de charge d'entraînement.")


def _render_zone_distribution(df: pd.DataFrame, ftp: float, has_data: bool):
    """Aggregated zone distribution across recent activities."""
    section_title("🎯", "Distribution par zone de puissance")

    # Show zone bounds
    bounds = zone_bounds_watts(ftp)
    zone_info = " · ".join([f"{name}: {lo:.0f}–{hi:.0f}W" for name, lo, hi in bounds[:5]])
    st.markdown(f"<div style='font-size:0.72rem;color:var(--text-d);margin-bottom:12px'>{zone_info}</div>",
                unsafe_allow_html=True)

    if has_data and "avg_power_w" in df.columns:
        # Aggregate zone time from stored data or compute from power
        # Use the visual horizontal bars approach
        recent = df.tail(20)
        zone_times = {z[0]: 0 for z in DEFAULT_ZONES}
        for _, row in recent.iterrows():
            p = row.get("avg_power_w")
            dur = row.get("duration_s", 0) or 0
            if p and p == p and dur > 0:
                for name, lo, hi in bounds:
                    if lo <= p < hi:
                        zone_times[name] += dur
                        break

        total = sum(zone_times.values())
        if total > 0:
            fig = go.Figure()
            zone_names = list(zone_times.keys())
            zone_pcts = [zone_times[z] / total * 100 for z in zone_names]

            for i, (zn, pct) in enumerate(zip(zone_names, zone_pcts)):
                color = ZONE_COLORS[i] if i < len(ZONE_COLORS) else C["text_m"]
                fig.add_trace(go.Bar(
                    y=[zn], x=[pct], orientation="h",
                    marker_color=color, name=zn,
                    text=f"{pct:.0f}%", textposition="inside",
                    showlegend=False,
                ))

            apply_plotly_theme(fig, height=280)
            fig.update_layout(
                xaxis_title="% du temps total",
                yaxis=dict(autorange="reversed"),
                bargap=0.3,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Pas de données de puissance dans les activités récentes.")
    else:
        # Demo zones
        fig = go.Figure()
        for i, z in enumerate(DEMO_ZONES):
            color = ZONE_COLORS[i] if i < len(ZONE_COLORS) else C["text_m"]
            fig.add_trace(go.Bar(
                y=[z["zone"]], x=[z["pct"]], orientation="h",
                marker_color=color, name=z["zone"],
                text=f"{z['pct']}%", textposition="inside",
                showlegend=False,
            ))
        apply_plotly_theme(fig, height=280)
        fig.update_layout(
            xaxis_title="% du temps",
            yaxis=dict(autorange="reversed"),
            bargap=0.3,
            annotations=[dict(text="Données de démonstration", xref="paper", yref="paper",
                              x=0.5, y=1.08, showarrow=False, font=dict(size=10, color=C["text_d"]))],
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_records(df: pd.DataFrame, ftp: float, weight: float, has_data: bool):
    """Personal records grid."""
    section_title("🏆", "Records personnels")

    if has_data:
        records = {
            "5s": df["best_5s_w"].max() if "best_5s_w" in df.columns else None,
            "1min": df["best_1m_w"].max() if "best_1m_w" in df.columns else None,
            "5min": df["best_5m_w"].max() if "best_5m_w" in df.columns else None,
            "20min": df["best_20m_w"].max() if "best_20m_w" in df.columns else None,
            "60min": df["best_60m_w"].max() if "best_60m_w" in df.columns else None,
        }
    else:
        records = {"5s": 820, "1min": 380, "5min": 310, "20min": 270, "60min": 250}

    cols = st.columns(len(records))
    for i, (dur, watts) in enumerate(records.items()):
        with cols[i]:
            wkg = f"{watts/weight:.2f}" if watts and weight > 0 else "—"
            stat_card(f"BEST {dur.upper()}", fmt_val(watts), "W")
            if watts and weight > 0:
                st.markdown(f"<div style='text-align:center;font-size:0.72rem;color:var(--text-m);margin-top:-8px'>"
                            f"{wkg} W/kg</div>", unsafe_allow_html=True)

    # W/kg trend chart
    if has_data and "watts_per_kg" in df.columns and "start_time" in df.columns:
        section_title("📊", "Évolution W/kg")
        wkg_data = df[["start_time", "watts_per_kg"]].dropna()
        if not wkg_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=wkg_data["start_time"], y=wkg_data["watts_per_kg"],
                mode="markers+lines",
                marker=dict(size=4, color=C["chart2"]),
                line=dict(color=C["chart2"], width=1.5),
                name="W/kg",
            ))
            # Trend line
            if len(wkg_data) > 3:
                z = np.polyfit(range(len(wkg_data)), wkg_data["watts_per_kg"].values, 1)
                trend = np.polyval(z, range(len(wkg_data)))
                fig.add_trace(go.Scatter(
                    x=wkg_data["start_time"], y=trend,
                    mode="lines", line=dict(color=C["chart3"], width=1, dash="dash"),
                    name="Tendance",
                ))
            apply_plotly_theme(fig, height=280)
            fig.update_layout(yaxis_title="W/kg")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
