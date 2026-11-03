"""
Gravel Coach V2 — Complete CSS stylesheet.

Injected once via st.markdown in the main entry point.
"""
from __future__ import annotations

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=Hind:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:          #1e1a16;
    --bg-alt:      #252119;
    --bg-card:     #2c2722;
    --bg-card-h:   #342e28;
    --bg-sidebar:  #181510;
    --bg-muted:    #3a342e;
    --border:      #3f3832;
    --border-l:    #4d453e;
    --text:        #f0ece8;
    --text-2:      #b5ada5;
    --text-m:      #8a8279;
    --text-d:      #6b6359;
    --primary:     #c4873a;
    --primary-h:   #d49544;
    --primary-fg:  #1a1612;
    --accent:      #6db56d;
    --accent-h:    #7ec97e;
    --red:         #c45a5a;
    --yellow:      #d4b74a;
    --blue:        #5ba0c4;
    --radius:      10px;
    --radius-sm:   6px;
    --radius-lg:   14px;
    --shadow:      0 1px 3px rgba(0,0,0,0.3);
    --shadow-lg:   0 4px 12px rgba(0,0,0,0.4);
    --transition:  0.15s ease;
}

/* ═══════════════════ RESET & FONTS ═══════════════════ */
html, body, [class*="st-"] {
    font-family: 'Hind', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
h1, h2, h3, h4, .font-display {
    font-family: 'Archivo', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.mono { font-family: 'JetBrains Mono', monospace !important; }

/* ═══════════════════ GLOBAL DARK ═══════════════════ */
.stApp, .main .block-container {
    background: var(--bg) !important;
    color: var(--text) !important;
}
.stApp { background-color: var(--bg) !important; }

/* Hide Streamlit default elements (keep sidebar toggle visible) */
#MainMenu, footer,
div[data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] {
    background: transparent !important;
    border: none !important;
    height: auto !important;
    min-height: 0 !important;
}
/* Hide the main menu area but keep sidebar expand button */
header[data-testid="stHeader"] [data-testid="stToolbar"] > div:not(:has([data-testid="stExpandSidebarButton"])) {
    display: none !important;
}
/* Style the sidebar expand button to match theme */
[data-testid="stExpandSidebarButton"] {
    color: var(--text-m) !important;
}
[data-testid="stExpandSidebarButton"]:hover {
    color: var(--primary) !important;
}

/* Reduce padding */
.main .block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-l); }

/* ═══════════════════ SIDEBAR ═══════════════════ */
section[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
    width: 260px !important;
    min-width: 260px !important;
}
section[data-testid="stSidebar"] > div {
    background: var(--bg-sidebar) !important;
    padding-top: 0.5rem !important;
}

/* Nav links */
section[data-testid="stSidebar"] .stRadio label {
    color: var(--text-2) !important;
    padding: 10px 16px !important;
    border-radius: 8px !important;
    margin-bottom: 2px !important;
    transition: all var(--transition);
    font-size: 0.9rem !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(196,135,58,0.08) !important;
    color: var(--text) !important;
}
section[data-testid="stSidebar"] .stRadio [data-checked="true"] + label,
section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background: rgba(196,135,58,0.12) !important;
    color: var(--primary) !important;
    font-weight: 600 !important;
}
/* Hide radio circles */
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] > div > div:first-child {
    display: none !important;
}

/* Sidebar expanders */
section[data-testid="stSidebar"] .streamlit-expanderHeader {
    font-size: 0.8rem !important;
    color: var(--text-m) !important;
    padding: 8px 0 !important;
}

/* Sidebar buttons */
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-2) !important;
    font-size: 0.8rem !important;
    border-radius: 6px !important;
    padding: 4px 12px !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}

/* ═══════════════════ CARDS ═══════════════════ */
.gc-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 16px;
}
.gc-card-muted {
    background: var(--bg-muted);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
}
.gc-card-hover {
    transition: all var(--transition);
    cursor: pointer;
}
.gc-card-hover:hover {
    border-color: var(--border-l);
    background: var(--bg-card-h);
    box-shadow: var(--shadow);
}

/* ═══════════════════ PAGE HEADER ═══════════════════ */
.gc-page-header {
    margin-bottom: 28px;
}
.gc-kicker {
    font-family: 'Archivo', sans-serif;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--primary);
    margin-bottom: 4px;
}
.gc-page-title {
    font-family: 'Archivo', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--text);
    line-height: 1.15;
    margin: 0;
}
.gc-page-subtitle {
    font-size: 0.85rem;
    color: var(--text-m);
    margin-top: 4px;
}

/* ═══════════════════ STAT CARDS ═══════════════════ */
.gc-stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
}
.gc-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.gc-stat-label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-m);
}
.gc-stat-row {
    display: flex;
    align-items: baseline;
    gap: 6px;
}
.gc-stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.55rem;
    font-weight: 500;
    color: var(--text);
    line-height: 1.2;
}
.gc-stat-unit {
    font-size: 0.7rem;
    color: var(--text-m);
}
.gc-stat-delta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 500;
}
.gc-delta-up { color: var(--accent); }
.gc-delta-down { color: var(--red); }
.gc-delta-neutral { color: var(--text-m); }

/* ═══════════════════ SECTION TITLE ═══════════════════ */
.gc-section-title {
    font-family: 'Archivo', sans-serif;
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.gc-section-title .icon {
    font-size: 0.85rem;
    opacity: 0.7;
}

/* ═══════════════════ COACH INSIGHT CARD ═══════════════════ */
.gc-coach-reco {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}
.gc-coach-reco::before {
    content: "";
    position: absolute;
    inset: 0;
    opacity: 0.03;
    background: repeating-radial-gradient(circle at 20% 50%, transparent 0, rgba(196,135,58,0.12) 40px),
                repeating-radial-gradient(circle at 80% 50%, transparent 0, rgba(196,135,58,0.08) 40px);
    pointer-events: none;
}
.gc-coach-reco-title {
    font-family: 'Archivo', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--primary);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.gc-coach-reco-text {
    color: var(--text-2);
    font-size: 0.88rem;
    line-height: 1.55;
    position: relative;
}

/* ═══════════════════ ACTIVITY ROW ═══════════════════ */
.gc-activity-row {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 8px;
    transition: all var(--transition);
    cursor: pointer;
}
.gc-activity-row:hover {
    border-color: var(--border-l);
    background: var(--bg-card-h);
}
.gc-activity-title {
    font-family: 'Archivo', sans-serif;
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text);
    margin-bottom: 2px;
}
.gc-activity-meta {
    font-size: 0.75rem;
    color: var(--text-m);
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}
.gc-activity-stats {
    display: flex;
    gap: 16px;
    margin-top: 8px;
}
.gc-activity-stat {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--text-2);
}
.gc-activity-stat span {
    color: var(--text-m);
    font-family: 'Hind', sans-serif;
    font-size: 0.7rem;
}

/* ═══════════════════ TAGS / PILLS ═══════════════════ */
.gc-tag {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.gc-tag-gravel { background: rgba(196,135,58,0.15); color: #c4873a; }
.gc-tag-route { background: rgba(91,160,196,0.15); color: #5ba0c4; }
.gc-tag-indoor { background: rgba(155,126,217,0.15); color: #9b7ed9; }
.gc-tag-bikepacking { background: rgba(109,181,109,0.15); color: #6db56d; }

/* Filter pills */
.gc-pills {
    display: flex;
    gap: 6px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}
.gc-pill {
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    transition: all var(--transition);
}
.gc-pill:hover {
    border-color: var(--primary);
    color: var(--primary);
}
.gc-pill.active {
    background: var(--primary);
    color: var(--primary-fg);
    border-color: var(--primary);
}

/* ═══════════════════ PROGRESS BAR ═══════════════════ */
.gc-progress-bg {
    background: var(--bg-muted);
    border-radius: 20px;
    height: 8px;
    overflow: hidden;
}
.gc-progress-fill {
    height: 100%;
    border-radius: 20px;
    background: linear-gradient(90deg, var(--primary), var(--yellow));
    transition: width 0.4s ease;
}

/* ═══════════════════ TABS ═══════════════════ */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    color: var(--text-m) !important;
    font-size: 0.85rem !important;
    padding: 10px 20px !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom-color: var(--primary) !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text) !important;
}

/* ═══════════════════ BUTTONS ═══════════════════ */
.stButton button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: var(--primary) !important;
    color: var(--primary-fg) !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}
.stButton button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background: var(--primary-h) !important;
}
.stButton button[kind="secondary"],
button[data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-2) !important;
    border-radius: 8px !important;
}
.stButton button[kind="secondary"]:hover,
button[data-testid="stBaseButton-secondary"]:hover {
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}

/* ═══════════════════ INPUTS ═══════════════════ */
.stNumberInput input, .stTextInput input, .stSelectbox select,
div[data-baseweb="input"] input, div[data-baseweb="select"] {
    background: var(--bg-muted) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
.stNumberInput label, .stTextInput label, .stSelectbox label {
    color: var(--text-m) !important;
    font-size: 0.8rem !important;
}

/* ═══════════════════ METRIC CARDS ═══════════════════ */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 16px !important;
}
[data-testid="stMetric"] label { color: var(--text-m) !important; }
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    color: var(--text) !important;
}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
}

/* ═══════════════════ EMPTY STATE ═══════════════════ */
.gc-empty-state {
    text-align: center;
    padding: 48px 24px;
    color: var(--text-m);
}
.gc-empty-state .icon {
    font-size: 2.5rem;
    margin-bottom: 12px;
    opacity: 0.5;
}
.gc-empty-state .title {
    font-family: 'Archivo', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-2);
    margin-bottom: 4px;
}
.gc-empty-state .desc {
    font-size: 0.85rem;
    max-width: 400px;
    margin: 0 auto;
    line-height: 1.5;
}

/* ═══════════════════ ZONE BARS ═══════════════════ */
.gc-zone-bar-bg {
    background: var(--bg-muted);
    border-radius: 4px;
    height: 24px;
    overflow: hidden;
    position: relative;
}
.gc-zone-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}
.gc-zone-label {
    font-size: 0.75rem;
    color: var(--text-2);
    font-weight: 500;
}
.gc-zone-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-m);
}

/* ═══════════════════ SETTINGS PAGE ═══════════════════ */
.gc-settings-section {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 20px;
}
.gc-settings-title {
    font-family: 'Archivo', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 4px;
}
.gc-settings-desc {
    font-size: 0.8rem;
    color: var(--text-m);
    margin-bottom: 16px;
}

/* ═══════════════════ RESPONSIVE ═══════════════════ */
@media (max-width: 768px) {
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    .gc-stat-value { font-size: 1.3rem; }
    .gc-page-title { font-size: 1.4rem; }
    .gc-activity-stats { flex-wrap: wrap; gap: 8px; }
}
</style>
"""
