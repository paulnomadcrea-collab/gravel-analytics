"""
Stockage local des activités synchronisées (SQLite).

On met en cache les données Garmin localement pour :
- éviter de re-télécharger à chaque ouverture du dashboard
- limiter la fréquence des appels à l'API non-officielle de Garmin
- garder un historique même si une activité est supprimée côté Garmin
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "gravel.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            activity_id INTEGER PRIMARY KEY,
            source TEXT DEFAULT 'garmin',
            start_time TEXT,
            name TEXT,
            activity_type TEXT,
            distance_m REAL,
            duration_s REAL,
            elevation_gain_m REAL,
            avg_speed_kmh REAL,
            max_speed_kmh REAL,
            avg_power_w REAL,
            max_power_w REAL,
            normalized_power_w REAL,
            avg_hr INTEGER,
            max_hr INTEGER,
            calories REAL,
            training_load REAL,
            tss REAL,
            avg_z2_power_w REAL,
            raw_json TEXT
        )
        """
    )
    # Migration : ajouter la colonne source si elle n'existe pas encore
    cursor = conn.execute("PRAGMA table_info(activities)")
    columns = {row[1] for row in cursor}
    if "source" not in columns:
        conn.execute("ALTER TABLE activities ADD COLUMN source TEXT DEFAULT 'garmin'")
        conn.commit()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS power_curve (
            activity_id INTEGER,
            duration_s INTEGER,
            power_w REAL,
            PRIMARY KEY (activity_id, duration_s)
        )
        """
    )
    conn.commit()
    return conn


def upsert_activity(conn: sqlite3.Connection, a: dict) -> None:
    # S'assurer que source est toujours présent
    if "source" not in a:
        a["source"] = "garmin"
    conn.execute(
        """
        INSERT INTO activities (
            activity_id, source, start_time, name, activity_type, distance_m, duration_s,
            elevation_gain_m, avg_speed_kmh, max_speed_kmh, avg_power_w, max_power_w,
            normalized_power_w, avg_hr, max_hr, calories, training_load, tss,
            avg_z2_power_w, raw_json
        ) VALUES (:activity_id, :source, :start_time, :name, :activity_type, :distance_m, :duration_s,
            :elevation_gain_m, :avg_speed_kmh, :max_speed_kmh, :avg_power_w, :max_power_w,
            :normalized_power_w, :avg_hr, :max_hr, :calories, :training_load, :tss,
            :avg_z2_power_w, :raw_json)
        ON CONFLICT(activity_id) DO UPDATE SET
            source=excluded.source,
            start_time=excluded.start_time, name=excluded.name,
            activity_type=excluded.activity_type, distance_m=excluded.distance_m,
            duration_s=excluded.duration_s, elevation_gain_m=excluded.elevation_gain_m,
            avg_speed_kmh=excluded.avg_speed_kmh, max_speed_kmh=excluded.max_speed_kmh,
            avg_power_w=excluded.avg_power_w, max_power_w=excluded.max_power_w,
            normalized_power_w=excluded.normalized_power_w, avg_hr=excluded.avg_hr,
            max_hr=excluded.max_hr, calories=excluded.calories,
            training_load=excluded.training_load, tss=excluded.tss,
            avg_z2_power_w=excluded.avg_z2_power_w, raw_json=excluded.raw_json
        """,
        a,
    )
    conn.commit()


def upsert_power_curve(conn: sqlite3.Connection, activity_id: int, curve: dict[int, float]) -> None:
    rows = [(activity_id, dur, watts) for dur, watts in curve.items()]
    conn.executemany(
        "INSERT OR REPLACE INTO power_curve (activity_id, duration_s, power_w) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()


def known_activity_ids(conn: sqlite3.Connection) -> set[int]:
    return {row[0] for row in conn.execute("SELECT activity_id FROM activities")}


def load_activities_df():
    import pandas as pd

    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM activities ORDER BY start_time", conn)
    conn.close()
    if not df.empty:
        df["start_time"] = pd.to_datetime(df["start_time"])
    return df


def load_best_power_curve():
    """Meilleure puissance jamais tenue pour chaque durée, tous rides confondus."""
    import pandas as pd

    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT duration_s, MAX(power_w) as power_w FROM power_curve GROUP BY duration_s ORDER BY duration_s",
        conn,
    )
    conn.close()
    return df
