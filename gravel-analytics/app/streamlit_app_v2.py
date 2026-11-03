"""
Gravel Coach V2 — Main entry point.

Modular architecture with separate page modules.
Launch: streamlit run app/streamlit_app_v2.py
"""
from __future__ import annotations

import streamlit as st

# ── Page config (must be first Streamlit call) ──
st.set_page_config(
    page_title="Gravel Coach",
    page_icon="🚴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialize session state ──
from components.state import init_state, load_activities, get_page
init_state()

# ── Inject CSS ──
from components.styles import CSS
st.markdown(CSS, unsafe_allow_html=True)

# ── Render sidebar & get current page ──
from components.sidebar import render_sidebar
current_page = render_sidebar()

# ── Load data ──
df = load_activities()

# ── Route to page ──
if current_page == "dashboard":
    from pages.dashboard import render
    render(df)
elif current_page == "activities":
    from pages.activities import render
    render(df)
elif current_page == "performance":
    from pages.performance import render
    render(df)
elif current_page == "coach":
    from pages.coach import render
    render(df)
elif current_page == "goals":
    from pages.goals import render
    render(df)
elif current_page == "settings":
    from pages.settings import render
    render(df)
else:
    from pages.dashboard import render
    render(df)

# ── Handle Strava OAuth callback ──
query_params = st.query_params
if "code" in query_params and "scope" in query_params:
    st.info("🔗 Callback Strava détecté — traitement en cours…")
    try:
        from strava_sync import handle_oauth_callback
        handle_oauth_callback(query_params["code"])
        st.success("✅ Strava connecté avec succès !")
        from components.state import clear_data_cache
        clear_data_cache()
    except Exception as ex:
        st.error(f"Erreur OAuth Strava : {ex}")
