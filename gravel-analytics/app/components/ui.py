"""
Gravel Coach V2 — Shared UI components.

Reusable HTML builders for stat cards, page headers, section titles,
empty states, activity rows, tags, progress bars, etc.
"""
from __future__ import annotations

import math
import datetime as dt
import streamlit as st


# ═══════════════════ PAGE HEADER ═══════════════════

def page_header(kicker: str, title: str, subtitle: str = ""):
    """Render the standard page header with kicker + title."""
    sub = f'<div class="gc-page-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div class="gc-page-header">
        <div class="gc-kicker">{kicker}</div>
        <div class="gc-page-title">{title}</div>
        {sub}
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════ SECTION TITLE ═══════════════════

def section_title(icon: str, text: str):
    """Small section heading inside a page."""
    st.markdown(f"""
    <div class="gc-section-title">
        <span class="icon">{icon}</span> {text}
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════ STAT CARD ═══════════════════

def stat_card(label: str, value, unit: str = "", delta=None, delta_suffix: str = ""):
    """Render a single stat card with optional delta indicator."""
    delta_html = ""
    if delta is not None:
        if isinstance(delta, (int, float)) and not math.isnan(delta):
            sign = "+" if delta > 0 else ""
            cls = "gc-delta-up" if delta > 0 else ("gc-delta-down" if delta < 0 else "gc-delta-neutral")
            delta_html = f'<span class="gc-stat-delta {cls}">{sign}{delta:.0f}{delta_suffix}</span>'
        elif isinstance(delta, str):
            delta_html = f'<span class="gc-stat-delta gc-delta-neutral">{delta}</span>'

    # Format value
    if isinstance(value, float):
        if value == value:  # not NaN
            value = f"{value:.1f}" if value % 1 else f"{value:.0f}"
        else:
            value = "—"
    elif value is None:
        value = "—"

    unit_html = f'<span class="gc-stat-unit">{unit}</span>' if unit else ""

    st.markdown(
        f'<div class="gc-stat-card"><div class="gc-stat">'
        f'<div class="gc-stat-label">{label}</div>'
        f'<div class="gc-stat-row"><span class="gc-stat-value">{value}</span>'
        f'{unit_html}{delta_html}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ═══════════════════ INLINE STAT (no card border) ═══════════════════

def stat_inline(label: str, value, unit: str = ""):
    """Compact stat display without card wrapper."""
    if isinstance(value, float):
        value = f"{value:.1f}" if (value == value and value % 1) else (f"{value:.0f}" if value == value else "—")
    elif value is None:
        value = "—"
    unit_html = f'<span class="gc-stat-unit">{unit}</span>' if unit else ""
    st.markdown(
        f'<div class="gc-stat"><div class="gc-stat-label">{label}</div>'
        f'<div class="gc-stat-row"><span class="gc-stat-value" style="font-size:1.3rem">{value}</span>'
        f'{unit_html}</div></div>',
        unsafe_allow_html=True,
    )


# ═══════════════════ COACH INSIGHT ═══════════════════

def coach_insight(title: str, text: str, icon: str = "🧠"):
    """Coach recommendation card with subtle background pattern."""
    st.markdown(f"""
    <div class="gc-coach-reco">
        <div class="gc-coach-reco-title">{icon} {title}</div>
        <div class="gc-coach-reco-text">{text}</div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════ CARD WRAPPER ═══════════════════

def card_start():
    """Open a card container."""
    st.markdown('<div class="gc-card">', unsafe_allow_html=True)


def card_end():
    """Close a card container."""
    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════ EMPTY STATE ═══════════════════

def empty_state(icon: str, title: str, description: str):
    """Centered empty state placeholder."""
    st.markdown(f"""
    <div class="gc-empty-state">
        <div class="icon">{icon}</div>
        <div class="title">{title}</div>
        <div class="desc">{description}</div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════ PROGRESS BAR ═══════════════════

def progress_bar(value: float, max_val: float = 1.0):
    """Custom progress bar (value between 0 and max_val)."""
    pct = min(100, max(0, (value / max_val) * 100)) if max_val > 0 else 0
    st.markdown(f"""
    <div class="gc-progress-bg">
        <div class="gc-progress-fill" style="width:{pct:.1f}%"></div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════ TAG / PILL ═══════════════════

def activity_tag(activity_type: str) -> str:
    """Returns HTML for an activity type tag."""
    t = (activity_type or "").lower()
    if "gravel" in t:
        return '<span class="gc-tag gc-tag-gravel">Gravel</span>'
    elif "route" in t or "road" in t or "cycling" in t:
        return '<span class="gc-tag gc-tag-route">Route</span>'
    elif "indoor" in t or "zwift" in t or "virtual" in t:
        return '<span class="gc-tag gc-tag-indoor">Indoor</span>'
    elif "bikepacking" in t:
        return '<span class="gc-tag gc-tag-bikepacking">Bikepacking</span>'
    else:
        return f'<span class="gc-tag gc-tag-route">{activity_type or "Ride"}</span>'


# ═══════════════════ FORMATTERS ═══════════════════

def fmt_duration(seconds) -> str:
    """Format seconds as Xh XXmin."""
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return "—"
    s = int(seconds)
    h, m = divmod(s // 60, 60)
    if h > 0:
        return f"{h}h {m:02d}min"
    return f"{m}min"


def fmt_km(meters) -> str:
    """Format meters as km with 1 decimal."""
    if meters is None or (isinstance(meters, float) and math.isnan(meters)):
        return "—"
    return f"{meters / 1000:.1f}"


def fmt_val(v, decimals: int = 0, fallback: str = "—") -> str:
    """Format a numeric value, return fallback for None/NaN."""
    if v is None:
        return fallback
    if isinstance(v, float) and math.isnan(v):
        return fallback
    if decimals == 0:
        return f"{v:.0f}"
    return f"{v:.{decimals}f}"


def fmt_date(d) -> str:
    """Format a date or datetime nicely in French."""
    MOIS = ["jan.", "fév.", "mars", "avr.", "mai", "juin",
            "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    if d is None:
        return "—"
    if isinstance(d, str):
        try:
            d = dt.datetime.fromisoformat(d)
        except Exception:
            return d
    if hasattr(d, "day"):
        return f"{d.day} {MOIS[d.month - 1]}"
    return str(d)


def greeting() -> str:
    """Time-of-day greeting in French."""
    h = dt.datetime.now().hour
    if h < 12:
        return "Bonjour"
    elif h < 18:
        return "Bon après-midi"
    return "Bonsoir"


# ═══════════════════ SETTINGS SECTION ═══════════════════

def settings_section(title: str, description: str = ""):
    """Start a settings section card."""
    desc = f'<div class="gc-settings-desc">{description}</div>' if description else ""
    st.markdown(f"""
    <div class="gc-settings-section">
        <div class="gc-settings-title">{title}</div>
        {desc}
    """, unsafe_allow_html=True)


def settings_section_end():
    st.markdown('</div>', unsafe_allow_html=True)
