"""
Gravel Coach V2 — Sidebar navigation.

Renders the permanent sidebar with:
  - Logo
  - Main navigation (6 pages)
  - Divider
  - Quick sync status
  - Version info
"""
from __future__ import annotations

import streamlit as st
from components.state import get_page, navigate_to


# ── Navigation definition ──
NAV_SECTIONS = [
    {"key": "dashboard",    "icon": "🏠", "label": "Tableau de bord"},
    {"key": "activities",   "icon": "🚴", "label": "Activités"},
    {"key": "performance",  "icon": "📊", "label": "Performance"},
    {"key": "coach",        "icon": "🧠", "label": "Coach IA"},
    {"key": "goals",        "icon": "⛰️", "label": "Objectifs"},
    # Separator handled in rendering
    {"key": "settings",     "icon": "⚙️", "label": "Paramètres"},
]


def render_sidebar():
    """Render the complete sidebar navigation."""
    with st.sidebar:
        # ── Logo ──
        st.markdown("""
        <div style="display:flex;align-items:center;gap:12px;padding:12px 8px 24px 8px">
            <div style="width:38px;height:38px;border-radius:10px;
                        background:linear-gradient(135deg,#c4873a,#d4b74a);
                        display:flex;align-items:center;justify-content:center;
                        font-family:'Archivo',sans-serif;font-weight:800;
                        font-size:1.15rem;color:#1a1612;flex-shrink:0">G</div>
            <div>
                <div style="font-family:'Archivo',sans-serif;font-weight:700;
                            font-size:0.95rem;color:#f0ece8;line-height:1.2">Gravel Coach</div>
                <div style="font-size:0.62rem;color:#6b6359;letter-spacing:0.05em">
                    ANALYSE & COACHING</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Build navigation items ──
        # We use radio for clean URL-free navigation
        nav_labels = []
        nav_keys = []
        separator_after = 4  # After "Objectifs"

        for item in NAV_SECTIONS:
            nav_labels.append(f"{item['icon']}  {item['label']}")
            nav_keys.append(item["key"])

        # Determine current index
        current_page = get_page()
        current_idx = 0
        for i, key in enumerate(nav_keys):
            if key == current_page:
                current_idx = i
                break

        # Insert separator before Settings via CSS-styled radio
        selected = st.radio(
            "Navigation",
            nav_labels,
            index=current_idx,
            label_visibility="collapsed",
            key="nav_radio",
        )

        # Update page from selection
        selected_idx = nav_labels.index(selected) if selected in nav_labels else 0
        new_page = nav_keys[selected_idx]
        if new_page != current_page:
            navigate_to(new_page)
            st.rerun()

        # ── Separator before settings ──
        st.markdown("""
        <hr style="border:none;border-top:1px solid #3f3832;margin:8px 0 4px 0">
        """, unsafe_allow_html=True)

        # ── Bottom info ──
        st.markdown("""
        <div style="position:fixed;bottom:16px;padding:0 16px">
            <div style="font-size:0.6rem;color:#6b6359;letter-spacing:0.05em">
                GRAVEL COACH v2.0
            </div>
        </div>
        """, unsafe_allow_html=True)

    return new_page
