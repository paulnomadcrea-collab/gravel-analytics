"""
Gravel Coach V2 — Goals page.

Goal tracking with progress visualization, event prep checklists.
"""
from __future__ import annotations

import datetime as dt
import plotly.graph_objects as go
import streamlit as st

from components.theme import C, apply_plotly_theme
from components.ui import (
    page_header, section_title, stat_card, empty_state,
    progress_bar, fmt_val,
)
from components.state import get_ftp, get_weight
from components.demo_data import DEMO_GOALS


def render(df):
    ftp = get_ftp()
    weight = get_weight()
    has_data = not df.empty

    page_header("OBJECTIFS", "Suivi de tes objectifs",
                "Progresse vers tes objectifs de performance")

    # ── Goals list ──
    goals = DEMO_GOALS  # TODO: load from DB when goal storage is implemented

    if not goals:
        empty_state("⛰️", "Aucun objectif défini",
                    "Définis tes objectifs pour suivre ta progression.")
        return

    for goal in goals:
        _render_goal_card(goal, ftp, weight)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Tips section ──
    section_title("💡", "Conseils pour atteindre tes objectifs")

    tips = [
        ("Sois spécifique", "Un objectif mesurable (FTP 280W) est plus efficace qu'un vague \"progresser\""),
        ("Décompose", "Divise un grand objectif en étapes intermédiaires de 4-6 semaines"),
        ("Sois patient", "La progression en endurance est lente — 1-2% par mois est un très bon rythme"),
        ("Ajuste", "Revois tes objectifs régulièrement en fonction de ta progression réelle"),
    ]

    for title, desc in tips:
        st.markdown(f"""
        <div style="display:flex;gap:12px;padding:8px 0;border-bottom:1px solid rgba(196,135,58,0.06)">
            <div style="font-family:'Archivo',sans-serif;font-weight:600;font-size:0.82rem;
                        color:var(--primary);min-width:130px">{title}</div>
            <div style="font-size:0.82rem;color:var(--text-m)">{desc}</div>
        </div>
        """, unsafe_allow_html=True)


def _render_goal_card(goal: dict, ftp: float, weight: float):
    """Render a single goal card with progress."""
    name = goal["name"]
    current = goal.get("current")
    target = goal.get("target")
    unit = goal.get("unit", "")
    deadline = goal.get("deadline", "")
    pct = goal.get("pct", 0)

    # Auto-calculate progress for FTP-based goals
    if target and current:
        pct = min(1.0, current / target) if target > 0 else 0

    pct_display = int(pct * 100)

    # Status color
    if pct >= 0.9:
        status_color = "#6db56d"  # green
        status_text = "Presque atteint !"
    elif pct >= 0.5:
        status_color = C["primary"]
        status_text = "En bonne voie"
    elif pct > 0:
        status_color = C["chart5"]
        status_text = "En cours"
    else:
        status_color = C["text_d"]
        status_text = "À démarrer"

    # Progress bar
    current_display = f"{current}{unit}" if current else "—"
    target_display = f"{target}{unit}" if target else "—"

    st.markdown(f"""
    <div class="gc-card" style="margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:12px">
            <div>
                <div style="font-family:'Archivo',sans-serif;font-weight:700;font-size:1rem;color:var(--text)">
                    ⛰️ {name}
                </div>
                <div style="font-size:0.72rem;color:var(--text-d);margin-top:2px">
                    Échéance : {deadline}
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:6px">
                <div style="width:8px;height:8px;border-radius:50%;background:{status_color}"></div>
                <span style="font-size:0.72rem;color:{status_color};font-weight:500">{status_text}</span>
            </div>
        </div>
        <div style="margin-bottom:8px">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:var(--text)">
                    {current_display}
                </span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:var(--text-d)">
                    {target_display}
                </span>
            </div>
            <div style="height:8px;background:rgba(196,135,58,0.1);border-radius:4px;overflow:hidden">
                <div style="height:100%;width:{pct_display}%;background:linear-gradient(90deg,{C['primary']},{C.get('accent', C['primary'])});
                            border-radius:4px;transition:width 0.3s ease"></div>
            </div>
            <div style="text-align:right;margin-top:4px">
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;
                            font-weight:600;color:var(--primary)">{pct_display}%</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
