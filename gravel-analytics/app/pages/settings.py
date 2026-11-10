"""
Gravel Coach V2 — Settings page.

Centralized settings: rider profile, connections (Garmin/Strava),
preferences, data management.
"""
from __future__ import annotations

import streamlit as st

from components.theme import C
from components.ui import (
    page_header, section_title, stat_card, empty_state,
    settings_section, settings_section_end,
)
from components.state import get_rider_profile, get_ftp, get_weight, clear_data_cache
import db


def render(df):
    page_header("PARAMÈTRES", "Configuration",
                "Gère ton profil, tes connexions et tes préférences")

    # ── Tabs for settings categories ──
    tab_profile, tab_connect, tab_data, tab_about = st.tabs([
        "👤 Profil",
        "🔗 Connexions",
        "💾 Données",
        "ℹ️ À propos",
    ])

    with tab_profile:
        _settings_profile()

    with tab_connect:
        _settings_connections()

    with tab_data:
        _settings_data(df)

    with tab_about:
        _settings_about()


def _settings_profile():
    """Rider profile settings."""
    section_title("👤", "Profil du coureur")

    settings_section("Informations physiques",
                     "Ces données sont utilisées pour calculer les zones de puissance, "
                     "le W/kg et les recommandations nutritionnelles.")

    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Nom", value=st.session_state.get("rider_name", "Gravel Rider"),
                             key="settings_name")
        ftp = st.number_input("FTP (Watts)", min_value=50, max_value=500,
                              value=int(st.session_state.get("ftp", 268)),
                              step=1, key="settings_ftp",
                              help="Functional Threshold Power — ta puissance seuil sur 1h")
        hr_rest = st.number_input("FC repos (bpm)", min_value=30, max_value=100,
                                  value=int(st.session_state.get("hr_rest", 48)),
                                  step=1, key="settings_hr_rest")

    with c2:
        weight = st.number_input("Poids (kg)", min_value=30.0, max_value=200.0,
                                 value=float(st.session_state.get("weight", 72)),
                                 step=0.5, key="settings_weight",
                                 help="Utilisé pour calculer le ratio W/kg")
        vo2max = st.number_input("VO₂max", min_value=20, max_value=90,
                                 value=int(st.session_state.get("vo2max", 54)),
                                 step=1, key="settings_vo2max")
        hr_max = st.number_input("FC max (bpm)", min_value=120, max_value=230,
                                 value=int(st.session_state.get("hr_max", 186)),
                                 step=1, key="settings_hr_max")

    settings_section_end()

    # Save button
    if st.button("💾 Enregistrer le profil", type="primary", key="save_profile"):
        st.session_state["rider_name"] = name
        st.session_state["ftp"] = ftp
        st.session_state["weight"] = weight
        st.session_state["hr_rest"] = hr_rest
        st.session_state["hr_max"] = hr_max
        st.session_state["vo2max"] = vo2max

        # Save FTP to history
        try:
            conn = db.get_conn()
            db.save_ftp(conn, ftp)
            conn.close()
        except Exception:
            pass

        clear_data_cache()
        st.success("✅ Profil enregistré")

    # W/kg display
    w = float(st.session_state.get("weight", 72))
    f = float(st.session_state.get("ftp", 268))
    if w > 0:
        wkg = f / w
        st.markdown(f"""
        <div style="margin-top:12px;padding:12px 16px;background:var(--card);border-radius:8px;
                    border:1px solid rgba(196,135,58,0.1)">
            <span style="font-size:0.82rem;color:var(--text-m)">Ratio W/kg actuel : </span>
            <span style="font-family:'JetBrains Mono',monospace;font-weight:600;
                        font-size:1rem;color:var(--primary)">{wkg:.2f} W/kg</span>
        </div>
        """, unsafe_allow_html=True)


def _settings_connections():
    """Sync connections settings."""
    section_title("🔗", "Sources de données")

    # ── Garmin Connect ──
    settings_section("Garmin Connect",
                     "Synchronise tes activités depuis Garmin Connect. "
                     "Nécessite ton email et ton mot de passe Garmin.")

    gc1, gc2 = st.columns(2)
    with gc1:
        garmin_email = st.text_input("Email Garmin", type="default",
                                     value=st.session_state.get("garmin_email", ""),
                                     key="settings_garmin_email")
    with gc2:
        garmin_pwd = st.text_input("Mot de passe Garmin", type="password",
                                   key="settings_garmin_pwd")

    garmin_days = st.slider("Nombre de jours à synchroniser", 7, 365, 30,
                            key="settings_garmin_days",
                            help="Nombre de jours d'historique à récupérer")

    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("🔄 Synchroniser Garmin", type="primary", key="sync_garmin"):
            if garmin_email and garmin_pwd:
                st.session_state["garmin_email"] = garmin_email
                _run_garmin_sync(garmin_email, garmin_pwd, garmin_days)
            else:
                st.warning("Renseigne ton email et mot de passe Garmin.")
    with bc2:
        # MFA input
        mfa_code = st.text_input("Code MFA (si demandé)", key="settings_mfa",
                                 help="Si l'authentification à deux facteurs est activée")

    settings_section_end()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Strava ──
    settings_section("Strava",
                     "Connexion via OAuth 2.0. Nécessite un compte développeur Strava.")

    sc1, sc2 = st.columns(2)
    with sc1:
        strava_id = st.text_input("Client ID", value=st.session_state.get("strava_client_id", ""),
                                  key="settings_strava_id")
    with sc2:
        strava_secret = st.text_input("Client Secret", type="password",
                                      value=st.session_state.get("strava_client_secret", ""),
                                      key="settings_strava_secret")

    if st.button("🔗 Connecter Strava", key="connect_strava"):
        if strava_id and strava_secret:
            st.session_state["strava_client_id"] = strava_id
            st.session_state["strava_client_secret"] = strava_secret
            st.info("Redirection vers Strava pour autorisation… (non implémenté en V2 preview)")
        else:
            st.warning("Renseigne le Client ID et le Client Secret Strava.")

    st.markdown("""
    <div style="font-size:0.72rem;color:var(--text-d);margin-top:8px">
        ⚠️ L'API Strava nécessite un abonnement payant depuis juin 2026.
    </div>
    """, unsafe_allow_html=True)

    settings_section_end()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── File import ──
    settings_section("Import de fichiers",
                     "Importe des fichiers FIT, GPX ou TCX directement.")

    uploaded = st.file_uploader(
        "Glisse un fichier ou clique pour parcourir",
        type=["fit", "gpx", "tcx"],
        key="settings_file_upload",
    )
    if uploaded:
        import hashlib
        import json
        from file_import import parse_file, extract_summary_from_df

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

    settings_section_end()


def _settings_data(df):
    """Data management settings."""
    section_title("💾", "Gestion des données")

    has_data = not df.empty

    # Database stats
    settings_section("Base de données",
                     "Statistiques de ta base de données locale.")

    if has_data:
        c1, c2, c3 = st.columns(3)
        with c1:
            stat_card("ACTIVITÉS", len(df), "")
        with c2:
            sources = df["source"].dropna().unique().tolist() if "source" in df.columns else []
            stat_card("SOURCES", len(sources), ", ".join(sources) if sources else "—")
        with c3:
            if "start_time" in df.columns:
                oldest = df["start_time"].min()
                stat_card("DEPUIS", oldest.strftime("%b %Y") if hasattr(oldest, "strftime") else "—", "")
            else:
                stat_card("DEPUIS", "—", "")
    else:
        st.info("Aucune activité dans la base de données.")

    settings_section_end()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Cache management
    settings_section("Cache",
                     "Vide le cache pour forcer le rechargement des données.")

    if st.button("🗑️ Vider le cache", key="clear_cache"):
        clear_data_cache()
        st.success("✅ Cache vidé. Les données seront rechargées au prochain affichage.")

    settings_section_end()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # FTP History
    settings_section("Historique FTP",
                     "Historique de tes valeurs FTP enregistrées.")

    ftp_df = db.load_ftp_history()
    if not ftp_df.empty:
        for _, row in ftp_df.iterrows():
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:6px 0;
                        border-bottom:1px solid rgba(196,135,58,0.06)">
                <span style="font-size:0.82rem;color:var(--text-m)">{row['date']}</span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;
                            font-weight:600;color:var(--text)">{row['ftp_w']}W</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="font-size:0.82rem;color:var(--text-d);padding:8px 0">
            Aucun historique FTP enregistré.
        </div>
        """, unsafe_allow_html=True)

    settings_section_end()


def _settings_about():
    """About section."""
    section_title("ℹ️", "À propos")

    st.markdown(f"""
    <div class="gc-card">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
            <div style="width:42px;height:42px;border-radius:10px;
                        background:linear-gradient(135deg,#c4873a,#d4b74a);
                        display:flex;align-items:center;justify-content:center;
                        font-family:'Archivo',sans-serif;font-weight:800;
                        font-size:1.2rem;color:#1a1612">G</div>
            <div>
                <div style="font-family:'Archivo',sans-serif;font-weight:700;
                            font-size:1.05rem;color:var(--text)">Gravel Coach</div>
                <div style="font-size:0.72rem;color:var(--text-d)">Version 2.0</div>
            </div>
        </div>
        <div style="font-size:0.82rem;color:var(--text-m);line-height:1.6">
            Application d'analyse et de coaching pour le cyclisme gravel.<br>
            Analyse tes performances, suis ta progression et reçois des recommandations personnalisées.
        </div>
        <div style="margin-top:16px;padding-top:12px;border-top:1px solid rgba(196,135,58,0.08)">
            <div style="font-size:0.72rem;color:var(--text-d)">
                Métriques basées sur les travaux de Coggan (zones, NP, TSS) et Banister (CTL/ATL/TSB).<br>
                Nutrition selon Jeukendrup (2014) et ACSM guidelines.
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Tech stack
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:0.72rem;color:var(--text-d);line-height:1.8">
        <strong>Stack technique</strong><br>
        Streamlit · Python · SQLite · Plotly · Garmin Connect API<br>
        FIT/GPX/TCX parsing · Coggan power zones · PMC (Banister)
    </div>
    """, unsafe_allow_html=True)


def _run_garmin_sync(email: str, password: str, days: int):
    """Execute Garmin sync with progress feedback."""
    with st.spinner("Connexion à Garmin Connect…"):
        try:
            import os
            from garmin_sync import login_step1
            from sync import sync_recent

            # Injecte les credentials saisies dans l'UI pour garmin_sync
            os.environ["GARMIN_EMAIL"] = email
            os.environ["GARMIN_PASSWORD"] = password

            status, client, client_state = login_step1()
            if status == "needs_mfa":
                st.session_state["garmin_mfa_client"] = client
                st.session_state["garmin_mfa_state"] = client_state
                st.warning("⚠️ Authentification MFA requise. Entre le code reçu par SMS/email ci-dessus puis relance la synchro.")
                return

            with st.spinner(f"Récupération des activités ({days} jours)…"):
                sync_recent(days_back=days, client=client)
                clear_data_cache()
                st.success(f"✅ Synchronisation terminée ! Rafraîchis la page pour voir les données.")
                st.rerun()

        except Exception as ex:
            error_msg = str(ex)
            if "MFA" in error_msg.upper() or "multi" in error_msg.lower():
                st.warning("⚠️ Authentification MFA requise. Entre le code reçu par SMS/email ci-dessus.")
            else:
                st.error(f"Erreur de synchronisation : {ex}")
