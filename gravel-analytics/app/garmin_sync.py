"""
Module de synchronisation avec Garmin Connect.

Utilise la librairie non-officielle `garminconnect` (reverse-engineering de
l'API web de Garmin Connect — il n'existe pas d'API publique officielle pour
les comptes particuliers).

Les identifiants NE SONT JAMAIS stockés en dur dans le code : ils sont lus
depuis des variables d'environnement (GARMIN_EMAIL / GARMIN_PASSWORD) ou
depuis st.secrets quand l'app tourne sur Streamlit.
"""
from __future__ import annotations

import os
import datetime as dt
from pathlib import Path
from typing import Optional

import garth
from garminconnect import Garmin, GarminConnectAuthenticationError

TOKEN_DIR = Path(os.environ.get("GARMIN_TOKEN_DIR", str(Path.home() / ".garminconnect")))

GRAVEL_KEYWORDS = ("gravel", "cycling", "road_biking", "mountain_biking")


def _get_credentials() -> tuple[str, str]:
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        try:
            import streamlit as st  # import local pour ne pas dépendre de streamlit hors app

            email = email or st.secrets.get("GARMIN_EMAIL")
            password = password or st.secrets.get("GARMIN_PASSWORD")
        except Exception:
            pass
    if not email or not password:
        raise RuntimeError(
            "Identifiants Garmin manquants. Définis GARMIN_EMAIL et GARMIN_PASSWORD "
            "(variables d'environnement ou secrets Streamlit)."
        )
    return email, password


def get_client() -> Garmin:
    """Retourne un client Garmin authentifié, en réutilisant le jeton de session
    stocké sur disque quand c'est possible (évite de se reconnecter à chaque
    appel et réduit le risque de blocage pour connexions trop fréquentes)."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    email, password = _get_credentials()

    try:
        garth.resume(str(TOKEN_DIR))
        client = Garmin(email=email, password=password)
        client.garth = garth.client
        client.display_name = garth.client.username
        # validation légère que le token est encore valide
        client.get_full_name()
        return client
    except Exception:
        pass

    client = Garmin(email=email, password=password)
    try:
        client.login()
    except GarminConnectAuthenticationError as e:
        raise RuntimeError(
            "Échec de connexion à Garmin Connect. Vérifie l'email/mot de passe, "
            "et qu'une validation en 2 étapes n'est pas requise."
        ) from e
    client.garth.dump(str(TOKEN_DIR))
    return client


def is_gravel_activity(activity: dict) -> bool:
    """Filtre les activités de type vélo. On garde tout ce qui est 'cycling'
    au sens large (Garmin ne distingue pas toujours 'gravel' explicitement),
    le filtrage fin se fait ensuite sur le nom/l'équipement si besoin."""
    activity_type = (activity.get("activityType") or {}).get("typeKey", "")
    return any(k in activity_type for k in GRAVEL_KEYWORDS)


def fetch_activities(
    client: Garmin,
    start: dt.date,
    end: Optional[dt.date] = None,
    only_cycling: bool = True,
    limit: int = 500,
) -> list[dict]:
    """Récupère les activités entre deux dates (incluses)."""
    end = end or dt.date.today()
    raw = client.get_activities_by_date(start.isoformat(), end.isoformat())
    if only_cycling:
        raw = [a for a in raw if is_gravel_activity(a)]
    return raw[:limit]


def fetch_activity_detail(client: Garmin, activity_id: int) -> dict:
    """Détails complets d'une activité : séries temporelles (puissance, FC,
    vitesse, altitude...) utilisées pour les analyses fines (zones, courbe
    de puissance)."""
    return client.get_activity_details(activity_id)


def fetch_power_curve(client: Garmin, activity_id: int) -> dict:
    try:
        return client.get_activity_power_curve(activity_id)
    except Exception:
        return {}
