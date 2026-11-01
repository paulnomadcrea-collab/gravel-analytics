"""
Module de synchronisation avec Strava.

Utilise l'API REST officielle v3 de Strava avec OAuth2.
Les identifiants (STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET) sont lus depuis
les variables d'environnement ou les secrets Streamlit.

Flux OAuth2 :
  1. L'utilisateur clique sur « Connecter Strava » → redirigé vers Strava
  2. Strava redirige vers l'app avec ?code=xxx
  3. L'app échange le code contre un access_token + refresh_token
  4. Les tokens sont sauvegardés localement pour réutilisation
"""
from __future__ import annotations

import json
import os
import time
import datetime as dt
from pathlib import Path
from typing import Optional

import requests

TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "strava_tokens.json"


def _get_credentials() -> tuple[str, str]:
    """Récupère Client ID et Client Secret Strava."""
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        try:
            import streamlit as st

            client_id = client_id or st.secrets.get("STRAVA_CLIENT_ID")
            client_secret = client_secret or st.secrets.get("STRAVA_CLIENT_SECRET")
        except Exception:
            pass
    if not client_id or not client_secret:
        raise RuntimeError(
            "Identifiants Strava manquants. Définis STRAVA_CLIENT_ID et "
            "STRAVA_CLIENT_SECRET (variables d'environnement ou secrets Streamlit)."
        )
    return client_id, client_secret


def get_auth_url(redirect_uri: str) -> str:
    """Génère l'URL d'autorisation Strava OAuth2."""
    client_id, _ = _get_credentials()
    return (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=read,activity:read_all"
        f"&approval_prompt=auto"
    )


def exchange_code(code: str) -> dict:
    """Échange le code d'autorisation contre des tokens d'accès."""
    client_id, client_secret = _get_credentials()
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    _save_tokens(tokens)
    return tokens


def _save_tokens(tokens: dict) -> None:
    """Sauvegarde les tokens sur disque."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2), encoding="utf-8")


def _load_tokens() -> Optional[dict]:
    """Charge les tokens depuis le disque."""
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def get_valid_token() -> Optional[str]:
    """Retourne un access_token valide, en le rafraîchissant si nécessaire.

    Retourne None si aucun token n'est enregistré (l'utilisateur doit
    d'abord passer par le flux OAuth2).
    """
    tokens = _load_tokens()
    if not tokens:
        return None

    # Rafraîchir si expiré (avec 60s de marge)
    if tokens.get("expires_at", 0) < time.time() + 60:
        client_id, client_secret = _get_credentials()
        resp = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        resp.raise_for_status()
        tokens = resp.json()
        _save_tokens(tokens)

    return tokens["access_token"]


def is_connected() -> bool:
    """Vérifie si un token Strava est enregistré (pas forcément valide)."""
    return _load_tokens() is not None


def disconnect() -> None:
    """Supprime les tokens Strava enregistrés."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


# ---------------------------------------------------------------- Fetch --


def fetch_activities(
    access_token: str,
    after: dt.date,
    before: Optional[dt.date] = None,
    per_page: int = 200,
) -> list[dict]:
    """Récupère les activités Strava entre deux dates.

    Strava pagine à 200 max par page — on boucle jusqu'à épuisement.
    """
    params: dict = {
        "after": int(dt.datetime.combine(after, dt.time.min).timestamp()),
        "per_page": per_page,
    }
    if before:
        params["before"] = int(
            dt.datetime.combine(before, dt.time.max).timestamp()
        )

    all_activities: list[dict] = []
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_activities.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return all_activities


def fetch_activity_streams(
    access_token: str, activity_id: int
) -> dict:
    """Récupère les séries temporelles (puissance, FC, vitesse, altitude)
    pour une activité Strava. Retourne un dict {type: {data: [...]}}."""
    resp = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "keys": "watts,heartrate,velocity_smooth,altitude,time",
            "key_by_type": "true",
        },
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return {}


def is_cycling_activity(activity: dict) -> bool:
    """Filtre les activités de type vélo (route, gravel, VTT, home trainer,
    Zwift...). On est large pour fusionner indoor + outdoor."""
    act_type = activity.get("type", "")
    sport_type = activity.get("sport_type", "")
    cycling_types = {
        "Ride", "VirtualRide", "GravelRide", "MountainBikeRide",
        "EBikeRide", "EMountainBikeRide", "Velomobile",
    }
    return act_type in cycling_types or sport_type in cycling_types
