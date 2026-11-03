"""
Gravel Coach V2 — Coach IA page.

Full coaching dashboard: fitness assessment, training recommendations,
zone analysis, nutrition advice, weekly program, performance trends.
"""
from __future__ import annotations

import datetime as dt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.theme import C, ZONE_COLORS, apply_plotly_theme
from components.ui import (
    page_header, section_title, stat_card, coach_insight,
    empty_state, fmt_duration, fmt_val,
)
from components.state import get_ftp, get_weight, get_rider_profile
from components.demo_data import DEMO_COACH_SUMMARY, DEMO_WEEK, DEMO_LOAD


def render(df: pd.DataFrame):
    ftp = get_ftp()
    weight = get_weight()
    rider = get_rider_profile()
    has_data = not df.empty

    page_header("COACH IA", "Analyse & recommandations",
                "Coaching personnalisé basé sur tes données")

    # ── Generate report ──
    report = None
    if has_data:
        from coach import generate_coach_report
        try:
            report = generate_coach_report(df, ftp=ftp, weight_kg=weight)
        except Exception:
            report = None

    if report:
        _render_full_report(report, ftp, weight)
    else:
        _render_demo_coach()


def _render_full_report(report, ftp: float, weight: float):
    """Render the full coach report with real data."""

    # ── Score global & état de forme ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_card("SCORE GLOBAL", report.overall_score, "/100")
    with c2:
        stat_card("ÉTAT DE FORME", report.fitness_emoji, report.fitness_status)
    with c3:
        stat_card("RÉGULARITÉ", report.consistency_score, "/100")
    with c4:
        stat_card("SORTIES/SEM", f"{report.rides_per_week_avg:.1f}", "")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Coach insight (summary) ──
    coach_insight("Résumé du coach", report.summary)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Tabs ──
    tab_fitness, tab_training, tab_nutrition, tab_program = st.tabs([
        "💪 Forme & tendances",
        "🎯 Recommandations",
        "🍎 Nutrition",
        "📅 Programme",
    ])

    with tab_fitness:
        _tab_fitness(report)

    with tab_training:
        _tab_training(report)

    with tab_nutrition:
        _tab_nutrition(report, weight)

    with tab_program:
        _tab_program()


def _tab_fitness(report):
    """Fitness assessment and trends tab."""
    section_title("🏋️", "État de forme")

    # Fitness detail
    st.markdown(f"""
    <div class="gc-card">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
            <span style="font-size:2rem">{report.fitness_emoji}</span>
            <div>
                <div style="font-family:'Archivo',sans-serif;font-weight:700;font-size:1.1rem;color:var(--text)">
                    {report.fitness_status}
                </div>
                <div style="font-size:0.82rem;color:var(--text-m);margin-top:2px">
                    {report.fitness_detail}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # PMC values
    if report.ctl is not None:
        c1, c2, c3 = st.columns(3)
        with c1:
            stat_card("CTL (FITNESS)", f"{report.ctl:.0f}", "")
        with c2:
            stat_card("ATL (FATIGUE)", f"{report.atl:.0f}", "")
        with c3:
            tsb_label = "Frais" if report.tsb > 5 else ("Forme" if report.tsb > -5 else "Fatigué")
            stat_card("TSB (FORME)", f"{report.tsb:+.0f}", tsb_label)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Volume stats
    section_title("📊", "Volume hebdomadaire moyen")
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        stat_card("HEURES/SEM", f"{report.weekly_hours_avg:.1f}", "h")
    with v2:
        stat_card("KM/SEM", f"{report.weekly_km_avg:.0f}", "km")
    with v3:
        stat_card("D+/SEM", f"{report.weekly_elevation_avg:.0f}", "m")
    with v4:
        stat_card("RÉGULARITÉ", f"{report.consistency_score}", "/100")

    st.markdown(f"""
    <div style="font-size:0.82rem;color:var(--text-m);margin-top:8px;padding:0 4px">
        {report.consistency_comment}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Trends
    if report.trend_details:
        section_title("📈", "Tendances de performance")
        for detail in report.trend_details:
            st.markdown(f"""
            <div style="font-size:0.85rem;color:var(--text);padding:8px 12px;
                        border-left:3px solid var(--primary);margin-bottom:8px;
                        background:rgba(196,135,58,0.04);border-radius:0 6px 6px 0">
                {detail}
            </div>
            """, unsafe_allow_html=True)

    # Zone distribution
    if report.zone_distribution:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section_title("🎯", "Répartition des zones")

        fig = go.Figure()
        zone_names = list(report.zone_distribution.keys())
        zone_pcts = list(report.zone_distribution.values())

        for i, (zn, pct) in enumerate(zip(zone_names, zone_pcts)):
            color = ZONE_COLORS[i] if i < len(ZONE_COLORS) else C["text_m"]
            fig.add_trace(go.Bar(
                y=[zn], x=[pct], orientation="h",
                marker_color=color, name=zn,
                text=f"{pct:.0f}%", textposition="inside",
                showlegend=False,
            ))

        apply_plotly_theme(fig, height=240)
        fig.update_layout(
            xaxis_title="% du temps",
            yaxis=dict(autorange="reversed"),
            bargap=0.3,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        if report.zone_comment:
            st.markdown(f"""
            <div style="font-size:0.82rem;color:var(--text-m);margin-top:4px;padding:0 4px">
                {report.zone_comment}
            </div>
            """, unsafe_allow_html=True)


def _tab_training(report):
    """Training recommendations tab."""
    section_title("🎯", "Recommandations d'entraînement")

    for rec in report.training_recommendations:
        st.markdown(f"""
        <div class="gc-card" style="margin-bottom:12px">
            <div style="font-size:0.88rem;color:var(--text);line-height:1.6">
                {rec}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Quick tips
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    section_title("💡", "Principes clés")

    tips = [
        ("Règle 80/20", "80% du temps en endurance (Z1-Z2), 20% en intensité (Z4+)"),
        ("Progression", "Augmente le volume de max 10% par semaine"),
        ("Récupération", "1 semaine allégée (-30%) toutes les 3-4 semaines"),
        ("Sommeil", "8h de sommeil = la meilleure récupération possible"),
        ("Spécificité", "Entraîne-toi sur le terrain de ton objectif (gravel, côtes, plat)"),
    ]

    for title, desc in tips:
        st.markdown(f"""
        <div style="display:flex;gap:12px;padding:8px 0;border-bottom:1px solid rgba(196,135,58,0.08)">
            <div style="font-family:'Archivo',sans-serif;font-weight:600;font-size:0.82rem;
                        color:var(--primary);min-width:120px">{title}</div>
            <div style="font-size:0.82rem;color:var(--text-m)">{desc}</div>
        </div>
        """, unsafe_allow_html=True)


def _tab_nutrition(report, weight: float):
    """Nutrition advice tab."""
    section_title("🍎", "Nutrition & Hydratation")

    advice = report.nutrition_advice

    # General recommendation card
    st.markdown(f"""
    <div class="gc-card">
        <div style="font-family:'Archivo',sans-serif;font-weight:600;font-size:0.88rem;color:var(--primary);
                    margin-bottom:8px">Sortie type : {advice.duration_category}</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px">
            <div class="gc-stat">
                <div class="gc-stat-label">Glucides/h</div>
                <div class="gc-stat-row">
                    <span class="gc-stat-value">{advice.carbs_per_hour_g[0]}–{advice.carbs_per_hour_g[1]}</span>
                    <span class="gc-stat-unit">g</span>
                </div>
            </div>
            <div class="gc-stat">
                <div class="gc-stat-label">Eau/h</div>
                <div class="gc-stat-row">
                    <span class="gc-stat-value">{advice.water_per_hour_ml[0]}–{advice.water_per_hour_ml[1]}</span>
                    <span class="gc-stat-unit">ml</span>
                </div>
            </div>
            <div class="gc-stat">
                <div class="gc-stat-label">Sodium/h</div>
                <div class="gc-stat-row">
                    <span class="gc-stat-value">{advice.electrolytes_mg_sodium_h[0]}–{advice.electrolytes_mg_sodium_h[1]}</span>
                    <span class="gc-stat-unit">mg</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Timing advice
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    timing_sections = [
        ("🌅 Avant la sortie", advice.pre_ride_meal),
        ("🚴 Pendant la sortie", "\n".join(f"• {item}" for item in advice.during_ride)),
        ("🏁 Après la sortie", advice.post_ride),
    ]

    for icon_title, content in timing_sections:
        st.markdown(f"""
        <div style="margin-bottom:12px;padding:12px 16px;background:var(--card);
                    border-radius:8px;border:1px solid rgba(196,135,58,0.08)">
            <div style="font-family:'Archivo',sans-serif;font-weight:600;font-size:0.82rem;
                        color:var(--text);margin-bottom:6px">{icon_title}</div>
            <div style="font-size:0.82rem;color:var(--text-m);line-height:1.6;white-space:pre-line">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Notes
    if advice.notes:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        section_title("📝", "Notes")
        for note in advice.notes:
            st.markdown(f"""
            <div style="font-size:0.82rem;color:var(--text-m);padding:4px 0 4px 16px;
                        border-left:2px solid rgba(196,135,58,0.15)">
                {note}
            </div>
            """, unsafe_allow_html=True)

    # Per-ride nutrition breakdown
    if report.ride_specific_nutrition:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section_title("📋", "Besoins par sortie récente")

        for ride_nut in report.ride_specific_nutrition:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        padding:8px 12px;margin-bottom:4px;background:var(--card);
                        border-radius:6px;border:1px solid rgba(196,135,58,0.06)">
                <div style="flex:1">
                    <div style="font-size:0.82rem;font-weight:600;color:var(--text)">{ride_nut['name']}</div>
                    <div style="font-size:0.72rem;color:var(--text-d)">{ride_nut['date']} · {ride_nut['duration_h']:.1f}h · {ride_nut['intensity']}</div>
                </div>
                <div style="display:flex;gap:16px;text-align:right">
                    <div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:var(--text)">{ride_nut['calories_estimated']}</div>
                        <div style="font-size:0.62rem;color:var(--text-d)">kcal</div>
                    </div>
                    <div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:var(--text)">{ride_nut['carbs_needed_g']}</div>
                        <div style="font-size:0.62rem;color:var(--text-d)">g glucides</div>
                    </div>
                    <div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:var(--text)">{ride_nut['water_needed_l']}</div>
                        <div style="font-size:0.62rem;color:var(--text-d)">L eau</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def _tab_program():
    """Weekly program tab."""
    section_title("📅", "Programme de la semaine")

    st.markdown("""
    <div style="font-size:0.82rem;color:var(--text-m);margin-bottom:16px">
        Programme suggéré basé sur ton profil et ta charge actuelle.
    </div>
    """, unsafe_allow_html=True)

    for day in DEMO_WEEK:
        check = "✓" if day["done"] else "○"
        color = C["accent"] if day["done"] else C["text_m"]
        opacity = "1" if day["done"] else "0.7"
        bg = "rgba(196,135,58,0.06)" if day["done"] else "transparent"

        st.markdown(f"""
        <div style="display:flex;gap:12px;align-items:center;padding:10px 12px;
                    opacity:{opacity};background:{bg};border-radius:6px;margin-bottom:4px">
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;
                        color:{color};width:18px;text-align:center">{check}</span>
            <span style="font-family:'Archivo',sans-serif;font-size:0.82rem;font-weight:600;
                        color:var(--text-2);width:40px">{day['day']}</span>
            <span style="font-size:0.82rem;color:var(--text-m);flex:1">{day['type']}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:0.72rem;color:var(--text-d);margin-top:12px;padding:0 4px">
        💡 Ce programme est un guide — adapte-le en fonction de ta forme du jour et de tes contraintes.
    </div>
    """, unsafe_allow_html=True)


def _render_demo_coach():
    """Demo coach view when no data is available."""
    coach_insight("Recommandation du coach", DEMO_COACH_SUMMARY)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Demo stats
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_card("SCORE GLOBAL", 78, "/100")
    with c2:
        stat_card("ÉTAT DE FORME", "🟢", "En forme")
    with c3:
        stat_card("RÉGULARITÉ", 72, "/100")
    with c4:
        stat_card("SORTIES/SEM", "3.2", "")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Demo tabs
    tab_fitness, tab_program = st.tabs(["💪 Forme", "📅 Programme"])

    with tab_fitness:
        st.markdown("""
        <div class="gc-card">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
                <span style="font-size:2rem">🟢</span>
                <div>
                    <div style="font-family:'Archivo',sans-serif;font-weight:700;font-size:1.1rem;color:var(--text)">
                        En forme
                    </div>
                    <div style="font-size:0.82rem;color:var(--text-m);margin-top:2px">
                        TSB à +7 — bon équilibre entre charge et récupération. Continue comme ça.
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        v1, v2, v3 = st.columns(3)
        with v1:
            stat_card("CTL (FITNESS)", f"{DEMO_LOAD['ctl']}", "")
        with v2:
            stat_card("ATL (FATIGUE)", f"{DEMO_LOAD['atl']}", "")
        with v3:
            stat_card("TSB (FORME)", f"+{DEMO_LOAD['tsb']}", "Frais")

        st.markdown("""
        <div style="text-align:center;font-size:0.75rem;color:var(--text-d);margin-top:12px">
            Données de démonstration — synchronise tes activités pour un coaching personnalisé.
        </div>
        """, unsafe_allow_html=True)

    with tab_program:
        _tab_program()
