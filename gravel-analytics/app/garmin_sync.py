"""
Module de synchronisation avec Garmin Connect.

Utilise la librairie non-officielle `garminconnect` (reverse-engineering de
l’API web de Garmin Connect — il n’existe pas d’API publique officielle pour
les comptes particuliers).

Les identifiants NE SONT JAMAIS stockés en dur dans le code : ils sont lus
depuis des variables d’environnement (GARMIN_EMAIL / GARMIN_PASSWORD) ou
depuis st.secrets quand l’app tourne sur Streamlit.

Gère la validation en 2 étapes (MFA) de manière interactive via l’UI
Streamlit : l’utilisateur reçoit un code par email/SMS et le saisit dans
l’app pour compléter la connexion.
"""
from __future__ import annotations

import os
import datetime as dt
from pathlib import Path
from typing import Optional

from garminconnect import Garmin, GarminConnectAuthenticationError

TOKEN_DIR = Path(os.environ.get("GARMIN_TOKEN_DIR", str(Path.home() / ".garminconnect")))
TOKEN_FILE = TOKEN_DIR / "tokens.json"

GRAVEL_KEYWORDS = ("gravel", "cycling", "road_biking", "mountain_biking")


def _get_credentials() -> tuple[str, str]:
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        try:
            import streamlit as st

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


def _load_tokenstore() -> str | None:
    """Charge le tokenstore JSON depuis le disque s'il existe."""
    if TOKEN_FILE.exists():
        try:
            return TOKEN_FILE.read_text(encoding="utf-8")
        except Exception:
            pass
    return None


def _save_tokenstore(client: Garmin) -> None:
    """Sauvegarde les tokens sur disque pour les réutiliser."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        client.client.dump(str(TOKEN_DIR / "session"))
    except Exception:
        pass


def login_step1() -> tuple[str | None, Garmin, object | None]:
    """Première étape de connexion.

    Retourne un tuple (status, client, client_state) :
      - (None, client, None)           -> connexion réussie, client prêt
      - ("needs_mfa", client, state)    -> MFA requis, appeler login_step2_mfa()
    """
    email, password = _get_credentials()
    tokenstore = _load_tokenstore()

    # Essai 1 : réutiliser les tokens sauvegardés
    if tokenstore:
        try:
            client = Garmin(email=email, password=password)
            client.login(tokenstore=tokenstore)
            return None, client, None
        except Exception:
            pass

    # Essai 2 : login avec credentials, mode MFA interactif
    client = Garmin(email=email, password=password, return_on_mfa=True)
    try:
        result = client.login()
        status, client_state = result

        if status == "needs_mfa":
            return "needs_mfa", client, client_state

        # Login réussi sans MFA
        _save_tokenstore(client)
        return None, client, None

    except GarminConnectAuthenticationError as e:
        raise RuntimeError(
            "Échec de connexion à Garmin Connect. Vérifie l'email/mot de passe."
        ) from e


def login_step2_mfa(client: Garmin, client_state: object, mfa_code: str) -> Garmin:
    """Complète la connexion avec le code MFA.

    Retourne le client authentifié.
    """
    try:
        client.resume_login(client_state, mfa_code)
    except Exception as e:
        raise RuntimeError(
            f"Code MFA invalide ou expiré. Réessaie avec un nouveau code. ({e})"
        ) from e

    _save_tokenstore(client)
    return client


def get_client() -> Garmin:
    """Retourne un client Garmin authentifié.

    Cette fonction ne gère PAS le flux MFA interactif — elle est prévue pour
    un usage en ligne de commande ou en tâche planifiée, où les tokens doivent
    déjà exister sur disque.

    Pour le flux interactif avec MFA (Streamlit), utiliser login_step1() /
    login_step2_mfa() depuis streamlit_app.py.
    """
    email, password = _get_credentials()
    tokenstore = _load_tokenstore()

    if tokenstore:
        try:
            client = Garmin(email=email, password=password)
            client.login(tokenstore=tokenstore)
            return client
        except Exception:
            pass

    # Fallback : login classique (échoue si MFA actif sans prompt)
    client = Garmin(email=email, password=password, prompt_mfa=lambda: input("Code MFA : "))
    try:
        client.login()
    except GarminConnectAuthenticationError as e:
        raise RuntimeError(
            "Échec de connexion à Garmin Connect. Vérifie l'email/mot de passe."
        ) from e
    _save_tokenstore(client)
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
