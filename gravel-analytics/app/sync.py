"""
Orchestration : récupère les sorties gravel depuis Garmin Connect, calcule les
métriques dérivées (NP, TSS, puissance moyenne en Z2...) et les stocke dans
la base locale. Pensé pour être appelé soit depuis le dashboard Streamlit
(bouton "Synchroniser"), soit en tâche planifiée (cron / scheduled task).
"""
from __future__ import annotations

import datetime as dt
import logging

import db
from analysis import normalized_power, parse_power_stream, time_and_avg_power_per_zone, training_stress_score
from garmin_sync import fetch_activities, fetch_activity_detail, fetch_power_curve, get_client

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


def sync_recent(days_back: int = 365, ftp: float = 250.0, fetch_detail: bool = True, client=None) -> int:
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
    activities = fetch_activities(client, start=start)

    count = 0
    for a in activities:
        row = _extract_summary(a)
        row["raw_json"] = json.dumps(a)

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = sync_recent()
    print(f"{n} activités synchronisées.")
