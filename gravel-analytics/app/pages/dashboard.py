"""
Gravel Coach V2 — Dashboard page.

Overview: greeting, coach insight, 4 KPI cards, fitness chart,
FTP history, last ride summary, weekly program.
"""
from __future__ import annotations

import datetime as dt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis import (
    performance_management_chart,
    training_stress_score,
    normalized_power,
    z2_progress,
)
from components.theme import C, PLOTLY_LAYOUT, apply_plotly_theme
from components.ui import (
    page_header, section_title, stat_card, coach_insight,
    empty_state, fmt_duration, fmt_km, fmt_val, fmt_date, greeting,
    activity_tag,
)
from components.state import get_rider_profile, get_ftp, get_weight
from components.demo_data import (
    DEMO_ACTIVITIES, DEMO_FTP_HISTORY, DEMO_LOAD,
    DEMO_WEEK, DEMO_COACH_SUMMARY,
)
import db


def render(df: pd.DataFrame):
    rider = get_rider_profile()
    ftp = get_ftp()
    weight = get_weight()
    has_data = not df.empty

    # ── Page header ──
    page_header(
        "TABLEAU DE BORD",
        f"{greeting()}, {rider['name']}",
        f"FTP {ftp}W · {weight}kg · VO₂max {rider['vo2max']}"
    )

    # ── Coach insight ──
    if has_data:
        from coach import generate_coach_report
        try:
            report = generate_coach_report(df, ftp=ftp, weight_kg=weight)
            coach_text = report.summary if report and report.summary else DEMO_COACH_SUMMARY
        except Exception:
            coach_text = DEMO_COACH_SUMMARY
    else:
        coach_text = DEMO_COACH_SUMMARY

    coach_insight("Recommandation du coach", coach_text)

    # ── 4 KPI Stats ──
    if has_data:
        # Compute PMC
        if "tss" in df.columns and "date" in df.columns:
            daily_tss = df.groupby("date")["tss"].sum()
            daily_tss.index = pd.to_datetime(daily_tss.index)
            if len(daily_tss) > 1:
                pmc = performance_management_chart(daily_tss)
                ctl = float(pmc["ctl"].iloc[-1])
                atl = float(pmc["atl"].iloc[-1])
                tsb = float(pmc["tsb"].iloc[-1])
            else:
                ctl, atl, tsb = 0, 0, 0
        else:
            ctl, atl, tsb = 0, 0, 0

        wkg = ftp / weight if weight > 0 else 0
    else:
        ctl = DEMO_LOAD["ctl"]
        atl = DEMO_LOAD["atl"]
        tsb = DEMO_LOAD["tsb"]
        wkg = ftp / weight if weight > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        stat_card("FTP", ftp, "W")
    with col2:
        stat_card("W/KG", f"{wkg:.2f}", "W/kg")
    with col3:
        stat_card("FITNESS (CTL)", f"{ctl:.0f}", "", delta=None)
    with col4:
        tsb_label = "Frais" if tsb > 5 else ("Forme" if tsb > -5 else "Fatigué")
        stat_card("FORME (TSB)", f"{tsb:+.0f}", tsb_label)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Charts row ──
    chart_col, ftp_col = st.columns([3, 2])

    with chart_col:
        section_title("📈", "Charge d'entraînement")
        if has_data and "tss" in df.columns and "date" in df.columns:
            daily_tss = df.groupby("date")["tss"].sum()
            daily_tss.index = pd.to_datetime(daily_tss.index)
            if len(daily_tss) > 1:
                pmc = performance_management_chart(daily_tss)
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pmc["date"], y=pmc["ctl"],
                    name="CTL (Fitness)", line=dict(color=C["chart2"], width=2),
                    fill="tozeroy", fillcolor="rgba(109,181,109,0.08)",
                ))
                fig.add_trace(go.Scatter(
                    x=pmc["date"], y=pmc["atl"],
                    name="ATL (Fatigue)", line=dict(color=C["chart5"], width=2),
                ))
                fig.add_trace(go.Scatter(
                    x=pmc["date"], y=pmc["tsb"],
                    name="TSB (Forme)", line=dict(color=C["chart4"], width=1.5, dash="dot"),
                ))
                fig.add_hline(y=0, line_color="rgba(77,69,62,0.6)", line_width=1)
                apply_plotly_theme(fig, height=280)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                _demo_pmc_chart()
        else:
            _demo_pmc_chart()

    with ftp_col:
        section_title("⚡", "Historique FTP")
        ftp_df = db.load_ftp_history()
        if not ftp_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=ftp_df["date"], y=ftp_df["ftp_w"],
                mode="lines+markers",
                line=dict(color=C["primary"], width=2),
                marker=dict(size=6, color=C["primary"]),
                name="FTP",
            ))
            apply_plotly_theme(fig, height=280)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            # Demo FTP chart
            fig = go.Figure()
            dates = [d["date"] for d in DEMO_FTP_HISTORY]
            vals = [d["ftp"] for d in DEMO_FTP_HISTORY]
            fig.add_trace(go.Scatter(
                x=dates, y=vals,
                mode="lines+markers",
                line=dict(color=C["primary"], width=2),
                marker=dict(size=6, color=C["primary"]),
                name="FTP",
            ))
            apply_plotly_theme(fig, height=280)
            fig.update_layout(
                annotations=[dict(
                    text="Données de démonstration",
                    xref="paper", yref="paper", x=0.5, y=1.05,
                    showarrow=False, font=dict(size=10, color=C["text_d"]),
                )]
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Last ride + Weekly program ──
    ride_col, week_col = st.columns([3, 2])

    with ride_col:
        section_title("🚴", "Dernière sortie")
        if has_data:
            last = df.iloc[-1]
            tag = activity_tag(str(last.get("activity_type", "")))
            name = last.get("name", "Sortie")
            date_str = fmt_date(last.get("start_time"))
            dist = fmt_km(last.get("distance_m"))
            dur = fmt_duration(last.get("duration_s"))
            elev = fmt_val(last.get("elevation_gain_m"))
            avg_p = fmt_val(last.get("avg_power_w"))
            np_w = fmt_val(last.get("normalized_power_w"))
            hr = fmt_val(last.get("avg_hr"))

            st.markdown(f"""
            <div class="gc-card">
                <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:12px">
                    <div>
                        <div style="font-family:'Archivo',sans-serif;font-weight:600;font-size:0.95rem;color:var(--text)">{name}</div>
                        <div style="font-size:0.75rem;color:var(--text-m);margin-top:2px">{date_str} · {last.get("source", "")}</div>
                    </div>
                    {tag}
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,1fr));gap:12px">
                    <div class="gc-stat">
                        <div class="gc-stat-label">Distance</div>
                        <div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{dist}</span><span class="gc-stat-unit">km</span></div>
                    </div>
                    <div class="gc-stat">
                        <div class="gc-stat-label">Durée</div>
                        <div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{dur}</span></div>
                    </div>
                    <div class="gc-stat">
                        <div class="gc-stat-label">Dénivelé</div>
                        <div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{elev}</span><span class="gc-stat-unit">m</span></div>
                    </div>
                    <div class="gc-stat">
                        <div class="gc-stat-label">Puiss. moy</div>
                        <div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{avg_p}</span><span class="gc-stat-unit">W</span></div>
                    </div>
                    <div class="gc-stat">
                        <div class="gc-stat-label">NP</div>
                        <div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{np_w}</span><span class="gc-stat-unit">W</span></div>
                    </div>
                    <div class="gc-stat">
                        <div class="gc-stat-label">FC moy</div>
                        <div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{hr}</span><span class="gc-stat-unit">bpm</span></div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            _demo_last_ride()

    with week_col:
        section_title("📅", "Programme semaine")
        for day in DEMO_WEEK:
            check = "✓" if day["done"] else "○"
            color = C["accent"] if day["done"] else C["text_m"]
            opacity = "1" if day["done"] else "0.7"
            st.markdown(f"""
            <div style="display:flex;gap:10px;align-items:center;padding:6px 0;opacity:{opacity}">
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:{color};width:16px">{check}</span>
                <span style="font-size:0.8rem;font-weight:600;color:var(--text-2);width:36px">{day['day']}</span>
                <span style="font-size:0.8rem;color:var(--text-m)">{day['type']}</span>
            </div>
            """, unsafe_allow_html=True)


def _demo_pmc_chart():
    """Render a demo PMC chart."""
    import random
    dates = pd.date_range(dt.date.today() - dt.timedelta(days=90), dt.date.today())
    ctl = np.cumsum(np.random.normal(0.5, 1.5, len(dates))) + 55
    atl = ctl + np.random.normal(0, 3, len(dates))
    tsb = ctl - atl

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=ctl, name="CTL", line=dict(color=C["chart2"], width=2),
                             fill="tozeroy", fillcolor="rgba(109,181,109,0.08)"))
    fig.add_trace(go.Scatter(x=dates, y=atl, name="ATL", line=dict(color=C["chart5"], width=2)))
    fig.add_trace(go.Scatter(x=dates, y=tsb, name="TSB", line=dict(color=C["chart4"], width=1.5, dash="dot")))
    fig.add_hline(y=0, line_color="rgba(77,69,62,0.6)", line_width=1)
    apply_plotly_theme(fig, height=280)
    fig.update_layout(
        annotations=[dict(
            text="Données de démonstration",
            xref="paper", yref="paper", x=0.5, y=1.05,
            showarrow=False, font=dict(size=10, color=C["text_d"]),
        )]
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _demo_last_ride():
    """Render demo last ride card."""
    a = DEMO_ACTIVITIES[0]
    from components.ui import activity_tag
    tag = activity_tag(a["type"])
    st.markdown(f"""
    <div class="gc-card">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:12px">
            <div>
                <div style="font-family:'Archivo',sans-serif;font-weight:600;font-size:0.95rem;color:var(--text)">{a['title']}</div>
                <div style="font-size:0.75rem;color:var(--text-m);margin-top:2px">{a['date']} · {a['source']} · Démo</div>
            </div>
            {tag}
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,1fr));gap:12px">
            <div class="gc-stat"><div class="gc-stat-label">Distance</div><div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{a['km']}</span><span class="gc-stat-unit">km</span></div></div>
            <div class="gc-stat"><div class="gc-stat-label">Durée</div><div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{a['duration_s']//3600}h{(a['duration_s']%3600)//60:02d}</span></div></div>
            <div class="gc-stat"><div class="gc-stat-label">Dénivelé</div><div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{a['dplus']}</span><span class="gc-stat-unit">m</span></div></div>
            <div class="gc-stat"><div class="gc-stat-label">Puiss. moy</div><div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{a['avgP']}</span><span class="gc-stat-unit">W</span></div></div>
            <div class="gc-stat"><div class="gc-stat-label">NP</div><div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{a['np']}</span><span class="gc-stat-unit">W</span></div></div>
            <div class="gc-stat"><div class="gc-stat-label">FC moy</div><div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.2rem">{a['hr']}</span><span class="gc-stat-unit">bpm</span></div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
