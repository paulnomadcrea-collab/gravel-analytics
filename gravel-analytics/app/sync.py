"""
Orchestration : récupère les sorties vélo depuis Garmin Connect et/ou Strava,
calcule les métriques dérivées (NP, TSS, puissance moyenne en Z2...) et les
stocke dans la base locale. Pensé pour être appelé soit depuis le dashboard
Streamlit (bouton "Synchroniser"), soit en tâche planifiée.
"""
from __future__ import annotations

import datetime as dt
import logging

import numpy as np
import pandas as pd

import db
from analysis import normalized_power, time_and_avg_power_per_zone, training_stress_score
from garmin_sync import (
    fetch_activities as garmin_fetch_activities,
    fetch_activity_detail,
    fetch_power_curve,
    get_client,
)
from analysis import parse_power_stream

log = logging.getLogger(__name__)


def _extract_summary(a: dict) -> dict:
    """Mappe les champs (parfois absents selon le type d'activité/l'appareil)
    du résumé Garmin vers notre schéma. Tout champ manquant devient None plutôt
    que de faire planter la synchro."""

    def g(*keys, default=None):
        for k in keys:
            if k in a and a[k] is not None:
                return a[k]
        return default

    avg_speed_ms = g("averageSpeed")
    max_speed_ms = g("maxSpeed")

    return {
        "activity_id": a["activityId"],
        "start_time": g("startTimeLocal", "startTimeGMT"),
        "name": g("activityName", default=""),
        "activity_type": (a.get("activityType") or {}).get("typeKey", ""),
        "distance_m": g("distance"),
        "duration_s": g("duration", "movingDuration"),
        "elevation_gain_m": g("elevationGain"),
        "avg_speed_kmh": avg_speed_ms * 3.6 if avg_speed_ms else None,
        "max_speed_kmh": max_speed_ms * 3.6 if max_speed_ms else None,
        "avg_power_w": g("avgPower"),
        "max_power_w": g("maxPower"),
        "normalized_power_w": g("normPower"),  # écrasé plus bas si on peut le recalculer
        "avg_hr": g("averageHR"),
        "max_hr": g("maxHR"),
        "calories": g("calories"),
        "training_load": g("activityTrainingLoad", "trainingLoadPeak"),
        "tss": None,
        "avg_z2_power_w": None,
        "raw_json": None,
    }


def sync_recent(days_back: int = 365, ftp: float = 250.0, fetch_detail: bool = True, client=None, weight_kg: float = 75.0) -> int:
    """Synchronise les activités des `days_back` derniers jours. Retourne le
    nombre d'activités nouvellement ajoutées ou mises à jour.

    Si `client` est fourni, il est utilisé directement (utile quand le flux
    MFA a déjà produit un client authentifié). Sinon, get_client() est appelé.
    """
    import json

    if client is None:
        client = get_client()
    conn = db.get_conn()

    start = dt.date.today() - dt.timedelta(days=days_back)
    activities = garmin_fetch_activities(client, start=start)

    count = 0
    for a in activities:
        row = _extract_summary(a)
        row["source"] = "garmin"
        row["raw_json"] = json.dumps(a)
        row["category"] = db.detect_category(row)
        if row.get("avg_power_w") and weight_kg > 0:
            row["watts_per_kg"] = round(row["avg_power_w"] / weight_kg, 2)
        else:
            row["watts_per_kg"] = None

        if fetch_detail:
            try:
                detail = fetch_activity_detail(client, row["activity_id"])
                power_df = parse_power_stream(detail)
                if not power_df.empty and power_df["power_w"].notna().any():
                    np_watts = normalized_power(power_df)
                    if np_watts == np_watts:  # pas NaN
                        row["normalized_power_w"] = np_watts
                        row["tss"] = training_stress_score(np_watts, ftp, row["duration_s"] or 0)
                    zdf = time_and_avg_power_per_zone(power_df, ftp)
                    z2 = zdf[zdf["zone"].str.startswith("Z2")]
                    if not z2.empty:
                        row["avg_z2_power_w"] = float(z2.iloc[0]["avg_power_w"])
            except Exception as e:  # une activité à problème ne doit pas bloquer la synchro
                log.warning("Détail indisponible pour l'activité %s : %s", row["activity_id"], e)

        db.upsert_activity(conn, row)
        count += 1

    conn.close()
    return count


def _extract_strava_summary(a: dict) -> dict:
    """Mappe les champs d'une activité Strava vers notre schéma."""
    distance = a.get("distance")  # en mètres
    moving_time = a.get("moving_time")  # en secondes
    elapsed_time = a.get("elapsed_time")
    avg_speed = a.get("average_speed")  # m/s
    max_speed = a.get("max_speed")  # m/s

    return {
        "activity_id": a["id"],
        "source": "strava",
        "start_time": a.get("start_date_local", a.get("start_date", "")),
        "name": a.get("name", ""),
        "activity_type": a.get("sport_type", a.get("type", "")),
        "distance_m": distance,
        "duration_s": moving_time or elapsed_time,
        "elevation_gain_m": a.get("total_elevation_gain"),
        "avg_speed_kmh": avg_speed * 3.6 if avg_speed else None,
        "max_speed_kmh": max_speed * 3.6 if max_speed else None,
        "avg_power_w": a.get("average_watts"),
        "max_power_w": a.get("max_watts"),
        "normalized_power_w": a.get("weighted_average_watts"),
        "avg_hr": a.get("average_heartrate"),
        "max_hr": a.get("max_heartrate"),
        "calories": a.get("calories"),
        "training_load": None,
        "tss": None,
        "avg_z2_power_w": None,
        "raw_json": None,
    }


def _parse_strava_power_stream(streams: dict) -> pd.DataFrame:
    """Convertit les streams Strava en DataFrame compatible avec analysis.py."""
    time_data = streams.get("time", {}).get("data", [])
    power_data = streams.get("watts", {}).get("data", [])
    hr_data = streams.get("heartrate", {}).get("data", [])
    speed_data = streams.get("velocity_smooth", {}).get("data", [])
    alt_data = streams.get("altitude", {}).get("data", [])

    if not time_data:
        return pd.DataFrame(columns=["elapsed_s", "power_w", "hr", "speed_kmh", "altitude_m"])

    n = len(time_data)
    df = pd.DataFrame({
        "elapsed_s": time_data,
        "power_w": power_data if len(power_data) == n else [np.nan] * n,
        "hr": hr_data if len(hr_data) == n else [np.nan] * n,
        "speed_kmh": [v * 3.6 if v is not None else np.nan for v in speed_data] if len(speed_data) == n else [np.nan] * n,
        "altitude_m": alt_data if len(alt_data) == n else [np.nan] * n,
    })
    return df


def sync_strava(
    access_token: str,
    days_back: int = 365,
    ftp: float = 250.0,
    fetch_detail: bool = True,
    weight_kg: float = 75.0,
) -> int:
    """Synchronise les activités Strava des `days_back` derniers jours.

    Retourne le nombre d'activités ajoutées ou mises à jour.
    """
    import json
    from strava_sync import fetch_activities as strava_fetch_activities
    from strava_sync import fetch_activity_streams, is_cycling_activity

    conn = db.get_conn()
    start = dt.date.today() - dt.timedelta(days=days_back)
    activities = strava_fetch_activities(access_token, after=start)

    # Filtrer uniquement les activités vélo
    activities = [a for a in activities if is_cycling_activity(a)]

    count = 0
    for a in activities:
        row = _extract_strava_summary(a)
        row["raw_json"] = json.dumps(a)
        row["category"] = db.detect_category(row)
        if row.get("avg_power_w") and weight_kg > 0:
            row["watts_per_kg"] = round(row["avg_power_w"] / weight_kg, 2)
        else:
            row["watts_per_kg"] = None

        if fetch_detail and a.get("device_watts", False):
            # Uniquement si l'activité a des données de puissance réelles
            try:
                streams = fetch_activity_streams(access_token, a["id"])
                if streams:
                    power_df = _parse_strava_power_stream(streams)
                    if not power_df.empty and power_df["power_w"].notna().any():
                        np_watts = normalized_power(power_df)
                        if np_watts == np_watts:  # pas NaN
                            row["normalized_power_w"] = np_watts
                            row["tss"] = training_stress_score(
                                np_watts, ftp, row["duration_s"] or 0
                            )
                        zdf = time_and_avg_power_per_zone(power_df, ftp)
                        z2 = zdf[zdf["zone"].str.startswith("Z2")]
                        if not z2.empty:
                            row["avg_z2_power_w"] = float(z2.iloc[0]["avg_power_w"])
            except Exception as e:
                log.warning(
                    "Streams indisponibles pour l'activité Strava %s : %s",
                    a["id"], e,
                )

        db.upsert_activity(conn, row)
        count += 1

    conn.close()
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = sync_recent()
    print(f"{n} activités Garmin synchronisées.")
