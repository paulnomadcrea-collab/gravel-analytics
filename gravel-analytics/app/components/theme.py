"""
Gravel Coach V2 — Design tokens & color palette.

Single source of truth for colors, fonts, Plotly layout defaults.
"""
from __future__ import annotations

# ── Color palette ──
C = {
    "bg":         "#1e1a16",
    "bg_alt":     "#252119",
    "card":       "#2c2722",
    "card_hover": "#342e28",
    "sidebar":    "#181510",
    "muted":      "#3a342e",
    "border":     "#3f3832",
    "border_l":   "#4d453e",
    "text":       "#f0ece8",
    "text2":      "#b5ada5",
    "text_m":     "#8a8279",
    "text_d":     "#6b6359",
    "primary":    "#c4873a",
    "primary_h":  "#d49544",
    "primary_fg": "#1a1612",
    "accent":     "#6db56d",
    "accent_h":   "#7ec97e",
    "red":        "#c45a5a",
    "red_h":      "#d06c6c",
    "yellow":     "#d4b74a",
    "blue":       "#5ba0c4",
    "chart1":     "#c4873a",
    "chart2":     "#6db56d",
    "chart3":     "#d4b74a",
    "chart4":     "#5ba0c4",
    "chart5":     "#c45a5a",
    "chart6":     "#9b7ed9",
}

# ── Chart colors list for Plotly sequences ──
CHART_COLORS = [C["chart1"], C["chart2"], C["chart3"], C["chart4"], C["chart5"], C["chart6"]]

# ── Zone colors (Z1–Z7) ──
ZONE_COLORS = ["#5ba0c4", "#6db56d", "#a8c74a", "#d4b74a", "#d4944a", "#c45a5a", "#9b4a9b"]

# ── Plotly layout defaults ──
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Hind, sans-serif", color=C["text2"], size=12),
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis=dict(
        gridcolor="rgba(63,56,50,0.5)",
        zerolinecolor="rgba(63,56,50,0.5)",
        tickfont=dict(size=11),
    ),
    yaxis=dict(
        gridcolor="rgba(63,56,50,0.5)",
        zerolinecolor="rgba(63,56,50,0.5)",
        tickfont=dict(size=11),
    ),
    legend=dict(
        font=dict(size=11, color=C["text2"]),
        bgcolor="rgba(0,0,0,0)",
        borderwidth=0,
    ),
    hoverlabel=dict(bgcolor=C["card"], font_size=12, font_family="Hind"),
)


def apply_plotly_theme(fig, height: int = 320, **overrides):
    """Apply the Gravel Coach theme to any Plotly figure."""
    layout = {**PLOTLY_LAYOUT, "height": height, **overrides}
    fig.update_layout(**layout)
    return fig
