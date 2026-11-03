"""
Gravel Coach V2 — Activities page.

Activity list with filters, search, sorting.
Activity detail view with full ride analysis.
"""
from __future__ import annotations

import json
import hashlib
import datetime as dt
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis import (
    best_efforts, normalized_power, training_stress_score,
    intensity_factor as calc_if, zone_bounds_watts,
    time_and_avg_power_per_zone, parse_power_stream,
)
from components.theme import C, ZONE_COLORS, apply_plotly_theme
from components.ui import (
    page_header, section_title, stat_card, empty_state,
    fmt_duration, fmt_km, fmt_val, fmt_date, activity_tag,
)
from components.state import get_ftp, get_weight, clear_data_cache
from components.demo_data import DEMO_ACTIVITIES
import db
from file_import import parse_file, extract_summary_from_df


def render(df: pd.DataFrame):
    ftp = get_ftp()
    weight = get_weight()
    has_data = not df.empty

    # Check if we're in detail view
    if st.session_state.get("activity_detail_id") is not None:
        _render_detail(df, ftp, weight)
        return

    # ── Page header ──
    page_header("ACTIVITÉS", "Historique des sorties",
                f"{len(df)} activités" if has_data else "Aucune activité")

    # ── File import ──
    with st.expander("📂 Importer un fichier (FIT / GPX / TCX)", expanded=False):
        uploaded = st.file_uploader(
            "Glissez un fichier ou cliquez pour parcourir",
            type=["fit", "gpx", "tcx"],
            key="file_upload_activities",
        )
        if uploaded:
            raw_bytes = uploaded.read()
            file_hash = hashlib.sha256(raw_bytes).hexdigest()
            uploaded.seek(0)
            conn = db.get_conn()
            if db.file_already_imported(conn, file_hash):
                st.info("Ce fichier a déjà été importé.")
            else:
                with st.spinner("Import en cours…"):
                    try:
                        rec_df = parse_file(uploaded.name, raw_bytes)
                        summary = extract_summary_from_df(rec_df)
                        activity_id = db.next_activity_id(conn)
                        summary["activity_id"] = activity_id
                        summary["source"] = "file"
                        summary["raw_json"] = json.dumps({"filename": uploaded.name})
                        db.upsert_activity(conn, summary)
                        db.save_ride_file(conn, activity_id, uploaded.name,
                                          uploaded.name.rsplit(".", 1)[-1].lower(), file_hash)
                        clear_data_cache()
                        st.success(f"✅ {uploaded.name} importé avec succès")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erreur d'import : {ex}")
            conn.close()

    # ── Filters ──
    if has_data:
        filter_cols = st.columns([2, 2, 2, 2, 4])
        with filter_cols[0]:
            types = ["Tout"] + sorted(df["activity_type"].dropna().unique().tolist()) if "activity_type" in df.columns else ["Tout"]
            sel_type = st.selectbox("Type", types, label_visibility="collapsed")
        with filter_cols[1]:
            sources = ["Toutes sources"] + sorted(df["source"].dropna().unique().tolist()) if "source" in df.columns else ["Toutes sources"]
            sel_source = st.selectbox("Source", sources, label_visibility="collapsed")
        with filter_cols[2]:
            categories = ["Toutes catégories"]
            if "category" in df.columns:
                categories += sorted(df["category"].dropna().unique().tolist())
            sel_cat = st.selectbox("Catégorie", categories, label_visibility="collapsed")
        with filter_cols[3]:
            sort_opts = {"Plus récentes": ("start_time", False), "Plus anciennes": ("start_time", True),
                         "Plus longues": ("distance_m", False), "Plus intenses": ("tss", False)}
            sel_sort = st.selectbox("Tri", list(sort_opts.keys()), label_visibility="collapsed")

        # Apply filters
        filtered = df.copy()
        if sel_type != "Tout":
            filtered = filtered[filtered["activity_type"] == sel_type]
        if sel_source != "Toutes sources":
            filtered = filtered[filtered["source"] == sel_source]
        if sel_cat != "Toutes catégories":
            filtered = filtered[filtered["category"] == sel_cat]

        sort_col, sort_asc = sort_opts[sel_sort]
        if sort_col in filtered.columns:
            filtered = filtered.sort_values(sort_col, ascending=sort_asc)

        # ── Activity list ──
        st.markdown(f"<div style='font-size:0.75rem;color:var(--text-m);margin-bottom:12px'>"
                    f"{len(filtered)} résultat{'s' if len(filtered) != 1 else ''}</div>",
                    unsafe_allow_html=True)

        for _, row in filtered.iterrows():
            _render_activity_row(row)
    else:
        # Demo mode
        empty_state("🚴", "Aucune activité",
                    "Synchronisez Garmin Connect ou importez un fichier FIT/GPX/TCX pour commencer.")
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section_title("📋", "Aperçu (données de démonstration)")
        for a in DEMO_ACTIVITIES:
            _render_demo_row(a)


def _render_activity_row(row):
    """Render a single activity row (clickable)."""
    tag = activity_tag(str(row.get("activity_type", "")))
    name = row.get("name", "Sortie sans nom")
    date_str = fmt_date(row.get("start_time"))
    dist = fmt_km(row.get("distance_m"))
    dur = fmt_duration(row.get("duration_s"))
    elev = fmt_val(row.get("elevation_gain_m"))
    avg_p = fmt_val(row.get("avg_power_w"))
    tss = fmt_val(row.get("tss"))
    source = row.get("source", "")
    aid = row.get("activity_id")

    st.markdown(f"""
    <div class="gc-activity-row" id="act-{aid}">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="flex:1">
                <div class="gc-activity-title">{name}</div>
                <div class="gc-activity-meta">
                    <span>{date_str}</span>
                    <span>{source}</span>
                    {tag}
                </div>
            </div>
            <div class="gc-activity-stats">
                <div class="gc-activity-stat">{dist} <span>km</span></div>
                <div class="gc-activity-stat">{dur}</div>
                <div class="gc-activity-stat">{elev} <span>m D+</span></div>
                <div class="gc-activity-stat">{avg_p} <span>W</span></div>
                <div class="gc-activity-stat">{tss} <span>TSS</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Detail button
    if aid is not None:
        if st.button(f"Voir détail ›", key=f"detail_{aid}", type="secondary"):
            st.session_state["activity_detail_id"] = aid
            st.rerun()


def _render_demo_row(a: dict):
    """Render a demo activity row."""
    tag = activity_tag(a.get("type", ""))
    dur_h = a["duration_s"] // 3600
    dur_m = (a["duration_s"] % 3600) // 60
    st.markdown(f"""
    <div class="gc-activity-row" style="opacity:0.8">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="flex:1">
                <div class="gc-activity-title">{a['title']}</div>
                <div class="gc-activity-meta">
                    <span>{a['date']}</span>
                    <span>{a['source']}</span>
                    {tag}
                </div>
            </div>
            <div class="gc-activity-stats">
                <div class="gc-activity-stat">{a['km']} <span>km</span></div>
                <div class="gc-activity-stat">{dur_h}h{dur_m:02d}</div>
                <div class="gc-activity-stat">{a['dplus']} <span>m D+</span></div>
                <div class="gc-activity-stat">{a['avgP']} <span>W</span></div>
                <div class="gc-activity-stat">{a['tss']} <span>TSS</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════ ACTIVITY DETAIL VIEW ═══════════════════

def _render_detail(df: pd.DataFrame, ftp: float, weight: float):
    """Render the detailed activity analysis view."""
    aid = st.session_state.get("activity_detail_id")

    # Back button
    if st.button("← Retour aux activités", type="secondary"):
        st.session_state["activity_detail_id"] = None
        st.rerun()

    if df.empty:
        empty_state("🚴", "Activité non trouvée", "")
        return

    # Find the activity
    match = df[df["activity_id"] == aid]
    if match.empty:
        empty_state("🚴", "Activité non trouvée", f"ID {aid} introuvable dans la base de données.")
        return

    row = match.iloc[0]
    name = row.get("name", "Sortie")
    date_str = fmt_date(row.get("start_time"))
    tag = activity_tag(str(row.get("activity_type", "")))

    # ── Header ──
    st.markdown(f"""
    <div class="gc-page-header">
        <div class="gc-kicker">DÉTAIL ACTIVITÉ</div>
        <div style="display:flex;align-items:center;gap:12px">
            <div class="gc-page-title" style="margin:0">{name}</div>
            {tag}
        </div>
        <div class="gc-page-subtitle">{date_str} · {row.get('source', '')}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── 8 stat cards ──
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1:
        stat_card("DISTANCE", fmt_km(row.get("distance_m")), "km")
    with r1c2:
        stat_card("DURÉE", fmt_duration(row.get("duration_s")), "")
    with r1c3:
        stat_card("DÉNIVELÉ", fmt_val(row.get("elevation_gain_m")), "m")
    with r1c4:
        stat_card("VITESSE MOY", fmt_val(row.get("avg_speed_kmh"), 1), "km/h")

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        stat_card("PUISSANCE MOY", fmt_val(row.get("avg_power_w")), "W")
    with r2c2:
        stat_card("NP", fmt_val(row.get("normalized_power_w")), "W")
    with r2c3:
        stat_card("TSS", fmt_val(row.get("tss")), "")
    with r2c4:
        stat_card("FC MOY", fmt_val(row.get("avg_hr")), "bpm")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Try to load power stream for detailed charts ──
    raw_json = row.get("raw_json")
    power_df = None
    if raw_json and isinstance(raw_json, str):
        try:
            detail = json.loads(raw_json)
            if "activityDetailMetrics" in detail:
                power_df = parse_power_stream(detail)
                if power_df.empty:
                    power_df = None
        except Exception:
            pass

    # ── Tabs for detailed analysis ──
    if power_df is not None:
        tab_ts, tab_zones, tab_efforts = st.tabs(["📈 Séries temporelles", "🎯 Zones", "🏆 Best efforts"])

        with tab_ts:
            _chart_time_series(power_df, ftp)

        with tab_zones:
            _chart_zones(power_df, ftp)

        with tab_efforts:
            _chart_best_efforts(power_df)
    else:
        # Show zone distribution from stored best efforts if available
        section_title("🏆", "Records personnels")
        cols_be = [("best_5s_w", "5s"), ("best_1m_w", "1min"), ("best_5m_w", "5min"),
                   ("best_20m_w", "20min"), ("best_60m_w", "60min")]
        be_cols = st.columns(len(cols_be))
        for i, (col_name, label) in enumerate(cols_be):
            with be_cols[i]:
                val = row.get(col_name)
                stat_card(label, fmt_val(val), "W")


def _chart_time_series(power_df: pd.DataFrame, ftp: float):
    """Power, HR, speed over time."""
    fig = go.Figure()
    if "power_w" in power_df.columns:
        fig.add_trace(go.Scatter(
            x=power_df["elapsed_s"] / 60, y=power_df["power_w"],
            name="Puissance", line=dict(color=C["chart1"], width=1.5),
            opacity=0.8,
        ))
        # 30s rolling
        if len(power_df) > 30:
            rolling = power_df["power_w"].rolling(30, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=power_df["elapsed_s"] / 60, y=rolling,
                name="Puissance (30s)", line=dict(color=C["primary"], width=2),
            ))
    if "hr" in power_df.columns and power_df["hr"].notna().any():
        fig.add_trace(go.Scatter(
            x=power_df["elapsed_s"] / 60, y=power_df["hr"],
            name="FC", line=dict(color=C["chart5"], width=1.5),
            yaxis="y2",
        ))
    fig.add_hline(y=ftp, line_color=C["primary"], line_width=1, line_dash="dash",
                  annotation_text=f"FTP {ftp}W", annotation_font_color=C["primary"])
    apply_plotly_theme(fig, height=350)
    fig.update_layout(
        xaxis_title="Minutes",
        yaxis_title="Watts",
        yaxis2=dict(title="BPM", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)", tickfont=dict(color=C["chart5"])),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _chart_zones(power_df: pd.DataFrame, ftp: float):
    """Zone distribution bar chart."""
    zone_df = time_and_avg_power_per_zone(power_df, ftp)
    total = zone_df["time_s"].sum()
    if total <= 0:
        return

    fig = go.Figure()
    for i, row in zone_df.iterrows():
        pct = row["time_s"] / total * 100
        color = ZONE_COLORS[i] if i < len(ZONE_COLORS) else C["text_m"]
        fig.add_trace(go.Bar(
            y=[row["zone"]], x=[pct], orientation="h",
            marker_color=color, name=row["zone"],
            text=f"{pct:.0f}%", textposition="inside",
            hovertemplate=f"{row['zone']}: {pct:.1f}% ({row['time_s']/60:.0f}min)<br>Puiss. moy: {row['avg_power_w']:.0f}W<extra></extra>",
        ))
    apply_plotly_theme(fig, height=280)
    fig.update_layout(
        barmode="stack",
        showlegend=False,
        xaxis_title="% du temps",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _chart_best_efforts(power_df: pd.DataFrame):
    """Best efforts bar chart."""
    efforts = best_efforts(power_df)
    labels = {5: "5s", 30: "30s", 60: "1min", 300: "5min", 600: "10min", 1200: "20min", 3600: "60min"}

    durations = []
    powers = []
    for dur in sorted(efforts.keys()):
        val = efforts[dur]
        if val == val:  # not NaN
            durations.append(labels.get(dur, f"{dur}s"))
            powers.append(val)

    if not powers:
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=durations, y=powers,
        marker_color=[C["chart1"] if i == powers.index(max(powers)) else C["muted"] for i in range(len(powers))],
        text=[f"{p:.0f}W" for p in powers],
        textposition="outside",
        textfont=dict(size=11, color=C["text2"]),
    ))
    apply_plotly_theme(fig, height=300)
    fig.update_layout(yaxis_title="Watts")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
