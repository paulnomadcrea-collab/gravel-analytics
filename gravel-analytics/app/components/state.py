"""
Gravel Coach V2 — Session state management.

Centralizes all session state initialization and access.
"""
from __future__ import annotations

import streamlit as st
import numpy as np
import pandas as pd

import db

# ── Default rider profile values ──
DEFAULTS = {
    "rider_name": "Paul",
    "ftp": 268,
    "weight": 72.0,
    "hr_rest": 48,
    "hr_max": 186,
    "vo2max": 54,
    "page": "dashboard",
    "activity_detail_id": None,
    "coach_messages": [],
}


def init_state():
    """Initialize all session state keys with defaults (idempotent)."""
    for key, default in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_rider_profile() -> dict:
    """Return current rider profile from session state."""
    return {
        "name": st.session_state.get("rider_name", DEFAULTS["rider_name"]),
        "weight": st.session_state.get("weight", DEFAULTS["weight"]),
        "ftp": st.session_state.get("ftp", DEFAULTS["ftp"]),
        "hr_rest": st.session_state.get("hr_rest", DEFAULTS["hr_rest"]),
        "hr_max": st.session_state.get("hr_max", DEFAULTS["hr_max"]),
        "vo2max": st.session_state.get("vo2max", DEFAULTS["vo2max"]),
    }


def get_ftp() -> int:
    return st.session_state.get("ftp", DEFAULTS["ftp"])


def get_weight() -> float:
    return st.session_state.get("weight", DEFAULTS["weight"])


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    """Load all activities from DB with caching."""
    df = db.load_activities_df()
    return df


def load_activities(weight: float = None) -> pd.DataFrame:
    """Load activities with computed columns."""
    df = load_data()
    if weight is None:
        weight = get_weight()
    if not df.empty:
        if "watts_per_kg" not in df.columns or df["watts_per_kg"].isna().all():
            df["watts_per_kg"] = df["avg_power_w"] / weight if weight > 0 else np.nan
        if "start_time" in df.columns:
            df["date"] = pd.to_datetime(df["start_time"]).dt.date
    return df


def clear_data_cache():
    """Clear the data cache after sync/import/settings change."""
    load_data.clear()


def navigate_to(page: str):
    """Set the current page."""
    st.session_state["page"] = page


def get_page() -> str:
    """Get current page."""
    return st.session_state.get("page", "dashboard")
