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
            category TEXT DEFAULT 'outdoor',
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
            watts_per_kg REAL,
            raw_json TEXT
        )
        """
    )
    # Migrations : ajouter les colonnes manquantes
    cursor = conn.execute("PRAGMA table_info(activities)")
    columns = {row[1] for row in cursor}
    if "source" not in columns:
        conn.execute("ALTER TABLE activities ADD COLUMN source TEXT DEFAULT 'garmin'")
    if "category" not in columns:
        conn.execute("ALTER TABLE activities ADD COLUMN category TEXT DEFAULT 'outdoor'")
    if "watts_per_kg" not in columns:
        conn.execute("ALTER TABLE activities ADD COLUMN watts_per_kg REAL")
    # Phase 1 — colonnes d'analyse détaillée
    for col_name in (
        "cadence_avg", "cadence_max",
        "best_5s_w", "best_1m_w", "best_5m_w", "best_20m_w", "best_60m_w",
        "difficulty_score", "intensity_factor",
    ):
        if col_name not in columns:
            conn.execute(f"ALTER TABLE activities ADD COLUMN {col_name} REAL")
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
    # Phase 1 — historique FTP
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ftp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ftp_w REAL NOT NULL,
            source TEXT DEFAULT 'manual',
            notes TEXT
        )
        """
    )
    # Phase 1 — fichiers importés
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ride_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER,
            filename TEXT NOT NULL,
            file_format TEXT,
            imported_at TEXT,
            file_hash TEXT,
            FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
        )
        """
    )
    conn.commit()
    return conn


INDOOR_ACTIVITY_TYPES = {
    "virtual_ride", "indoor_cycling", "indoor_biking",
    "virtual_ride_zwift", "cycling_virtual", "stationary_cycling",
}

ZWIFT_KEYWORDS = {"zwift", "watopia", "innsbruck", "richmond", "london",
                  "new york", "paris", "makuri", "france", "scotland", "yorkshire"}


def detect_category(a: dict) -> str:
    """Détecte la catégorie d'une activité : 'indoor_zwift', 'indoor', ou 'outdoor'.

    Logique :
    1. Le type d'activité Garmin contient virtual/indoor → indoor
    2. Le nom de l'activité contient des mots-clés Zwift → indoor_zwift
    3. Distance nulle/très faible + puissance → indoor (home trainer)
    4. Sinon → outdoor
    """
    activity_type = (a.get("activity_type") or "").lower()
    name = (a.get("name") or "").lower()

    # Vérifier le type d'activité
    is_indoor_type = any(t in activity_type for t in ("virtual", "indoor", "stationary"))

    # Vérifier les mots-clés Zwift dans le nom
    is_zwift = any(kw in name for kw in ZWIFT_KEYWORDS)

    # Vérifier aussi dans le raw_json si dispo
    raw = a.get("raw_json") or ""
    if isinstance(raw, str):
        raw_lower = raw.lower()
        if not is_zwift:
            is_zwift = any(kw in raw_lower for kw in ("zwift", "virtualride"))

    if is_zwift or (is_indoor_type and "zwift" in name):
        return "indoor_zwift"
    elif is_indoor_type:
        return "indoor"
    elif a.get("distance_m") is not None and a["distance_m"] == 0 and a.get("avg_power_w"):
        return "indoor"
    else:
        return "outdoor"


_ACTIVITY_COLUMNS = [
    "activity_id", "source", "category", "start_time", "name", "activity_type",
    "distance_m", "duration_s", "elevation_gain_m", "avg_speed_kmh", "max_speed_kmh",
    "avg_power_w", "max_power_w", "normalized_power_w", "avg_hr", "max_hr",
    "calories", "training_load", "tss", "avg_z2_power_w", "watts_per_kg",
    "cadence_avg", "cadence_max",
    "best_5s_w", "best_1m_w", "best_5m_w", "best_20m_w", "best_60m_w",
    "difficulty_score", "intensity_factor",
    "raw_json",
]


def upsert_activity(conn: sqlite3.Connection, a: dict) -> None:
    # S'assurer que source et category sont toujours présents
    if "source" not in a:
        a["source"] = "garmin"
    if "category" not in a:
        a["category"] = detect_category(a)
    # Remplir les colonnes manquantes avec None
    for col in _ACTIVITY_COLUMNS:
        if col not in a:
            a[col] = None

    cols_str = ", ".join(_ACTIVITY_COLUMNS)
    vals_str = ", ".join(f":{c}" for c in _ACTIVITY_COLUMNS)
    update_str = ", ".join(f"{c}=excluded.{c}" for c in _ACTIVITY_COLUMNS if c != "activity_id")

    conn.execute(
        f"""
        INSERT INTO activities ({cols_str})
        VALUES ({vals_str})
        ON CONFLICT(activity_id) DO UPDATE SET {update_str}
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


# ─────────────── Phase 1 — ride_files helpers ───────────────

def save_ride_file(conn: sqlite3.Connection, activity_id: int, filename: str,
                   file_format: str, file_hash: str) -> None:
    """Enregistre un fichier importé dans ride_files (évite les doublons par hash)."""
    import datetime as _dt
    existing = conn.execute(
        "SELECT id FROM ride_files WHERE file_hash = ?", (file_hash,)
    ).fetchone()
    if existing:
        return  # déjà importé
    conn.execute(
        """INSERT INTO ride_files (activity_id, filename, file_format, imported_at, file_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (activity_id, filename, file_format, _dt.datetime.now().isoformat(), file_hash),
    )
    conn.commit()


def file_already_imported(conn: sqlite3.Connection, file_hash: str) -> bool:
    """Vérifie si un fichier a déjà été importé (par hash SHA-256)."""
    row = conn.execute("SELECT id FROM ride_files WHERE file_hash = ?", (file_hash,)).fetchone()
    return row is not None


# ─────────────── Phase 1 — ftp_history helpers ───────────────

def save_ftp(conn: sqlite3.Connection, date: str, ftp_w: float,
             source: str = "manual", notes: str = "") -> None:
    conn.execute(
        "INSERT INTO ftp_history (date, ftp_w, source, notes) VALUES (?, ?, ?, ?)",
        (date, ftp_w, source, notes),
    )
    conn.commit()


def load_ftp_history():
    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM ftp_history ORDER BY date", conn)
    conn.close()
    return df


def next_activity_id(conn: sqlite3.Connection) -> int:
    """Génère un ID unique pour une activité importée par fichier (négatif pour éviter les conflits Garmin/Strava)."""
    row = conn.execute("SELECT MIN(activity_id) FROM activities").fetchone()
    min_id = row[0] if row and row[0] is not None else 0
    return min(min_id, 0) - 1
