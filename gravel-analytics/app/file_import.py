"""
Import de fichiers FIT, GPX et TCX.

Chaque parser produit un DataFrame normalisé avec les colonnes :
    elapsed_s, power_w, hr, speed_kmh, altitude_m, cadence, lat, lon

Ce format est identique à celui de parse_power_stream() dans analysis.py,
ce qui permet de réutiliser tout le pipeline d'analyse existant.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

EXPECTED_COLUMNS = ["elapsed_s", "power_w", "hr", "speed_kmh", "altitude_m", "cadence", "lat", "lon"]


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=EXPECTED_COLUMNS)


# ─────────────────────────── FIT ───────────────────────────

def parse_fit(file_bytes: bytes) -> pd.DataFrame:
    """Parse un fichier FIT et retourne un DataFrame normalisé."""
    try:
        import fitdecode
    except ImportError:
        log.error("fitdecode non installé — pip install fitdecode")
        return _empty_df()

    rows: list[dict] = []
    start_ts = None

    with fitdecode.FitReader(io.BytesIO(file_bytes)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue
            if frame.name != "record":
                continue

            # Timestamp → elapsed_s
            ts = frame.get_value("timestamp", fallback=None)
            if ts is None:
                continue
            if start_ts is None:
                start_ts = ts
            elapsed = (ts - start_ts).total_seconds()

            row = {
                "elapsed_s": elapsed,
                "power_w": frame.get_value("power", fallback=np.nan),
                "hr": frame.get_value("heart_rate", fallback=np.nan),
                "cadence": frame.get_value("cadence", fallback=np.nan),
                "altitude_m": frame.get_value("altitude", fallback=np.nan),
                "lat": None,
                "lon": None,
                "speed_kmh": np.nan,
            }

            # Vitesse : enhanced_speed ou speed (m/s → km/h)
            speed_ms = frame.get_value("enhanced_speed", fallback=None)
            if speed_ms is None:
                speed_ms = frame.get_value("speed", fallback=None)
            if speed_ms is not None:
                row["speed_kmh"] = speed_ms * 3.6

            # Position GPS (semicircles → degrés)
            lat_raw = frame.get_value("position_lat", fallback=None)
            lon_raw = frame.get_value("position_long", fallback=None)
            if lat_raw is not None and lon_raw is not None:
                # fitdecode retourne déjà en degrés pour les SDK récents,
                # mais certains fichiers ont des semicircles
                if isinstance(lat_raw, (int,)) and abs(lat_raw) > 360:
                    row["lat"] = lat_raw * (180 / 2**31)
                    row["lon"] = lon_raw * (180 / 2**31)
                else:
                    row["lat"] = float(lat_raw)
                    row["lon"] = float(lon_raw)

            rows.append(row)

    if not rows:
        return _empty_df()

    df = pd.DataFrame(rows)
    # Assurer toutes les colonnes
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[EXPECTED_COLUMNS]


# ─────────────────────────── GPX ───────────────────────────

def parse_gpx(file_bytes: bytes) -> pd.DataFrame:
    """Parse un fichier GPX et retourne un DataFrame normalisé.

    Supporte les extensions Garmin (TrackPointExtension) et Wahoo pour
    la puissance, la FC et la cadence.
    """
    try:
        import gpxpy
    except ImportError:
        log.error("gpxpy non installé — pip install gpxpy")
        return _empty_df()

    gpx = gpxpy.parse(file_bytes.decode("utf-8", errors="replace"))
    rows: list[dict] = []
    start_ts = None
    prev_point = None

    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if start_ts is None:
                    start_ts = pt.time
                if pt.time is None or start_ts is None:
                    continue
                elapsed = (pt.time - start_ts).total_seconds()

                row = {
                    "elapsed_s": elapsed,
                    "power_w": np.nan,
                    "hr": np.nan,
                    "cadence": np.nan,
                    "altitude_m": pt.elevation if pt.elevation is not None else np.nan,
                    "lat": pt.latitude,
                    "lon": pt.longitude,
                    "speed_kmh": np.nan,
                }

                # Vitesse via gpxpy (entre deux points)
                if prev_point is not None and pt.time != prev_point.time:
                    speed = pt.speed_between(prev_point)
                    if speed is not None:
                        row["speed_kmh"] = speed * 3.6

                # Extensions GPX (Garmin TrackPointExtension, Wahoo, etc.)
                if pt.extensions:
                    row.update(_parse_gpx_extensions(pt.extensions))

                rows.append(row)
                prev_point = pt

    if not rows:
        return _empty_df()

    df = pd.DataFrame(rows)
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[EXPECTED_COLUMNS]


def _parse_gpx_extensions(extensions) -> dict:
    """Extrait power/hr/cadence depuis les extensions GPX XML."""
    result = {}
    for ext in extensions:
        # Parcourir récursivement les éléments XML
        _extract_from_xml(ext, result)
    return result


def _extract_from_xml(element, result: dict):
    """Extraction récursive des valeurs depuis un élément XML d'extension GPX."""
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    tag_lower = tag.lower()

    if tag_lower in ("hr", "heartrate", "heartratebpm"):
        # Peut contenir un sous-élément <Value>
        val = element.text
        if val is None:
            for child in element:
                child_tag = child.tag.split("}")[-1].lower()
                if child_tag == "value" and child.text:
                    val = child.text
                    break
        if val:
            try:
                result["hr"] = float(val)
            except ValueError:
                pass
    elif tag_lower in ("power", "watts"):
        if element.text:
            try:
                result["power_w"] = float(element.text)
            except ValueError:
                pass
    elif tag_lower in ("cad", "cadence"):
        if element.text:
            try:
                result["cadence"] = float(element.text)
            except ValueError:
                pass
    else:
        # Descendre dans les enfants
        for child in element:
            _extract_from_xml(child, result)


# ─────────────────────────── TCX ───────────────────────────

def parse_tcx(file_bytes: bytes) -> pd.DataFrame:
    """Parse un fichier TCX et retourne un DataFrame normalisé."""
    try:
        from lxml import etree
    except ImportError:
        log.error("lxml non installé — pip install lxml")
        return _empty_df()

    NS = {"tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
          "ext": "http://www.garmin.com/xmlschemas/ActivityExtension/v2"}

    tree = etree.parse(io.BytesIO(file_bytes))
    root = tree.getroot()
    rows: list[dict] = []
    start_ts = None

    trackpoints = root.findall(".//tcx:Trackpoint", NS)

    for tp in trackpoints:
        time_el = tp.find("tcx:Time", NS)
        if time_el is None or not time_el.text:
            continue

        from datetime import datetime, timezone
        ts_str = time_el.text
        # Formats ISO courants
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                ts = datetime.strptime(ts_str, fmt)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            continue

        if start_ts is None:
            start_ts = ts
        elapsed = (ts - start_ts).total_seconds()

        row = {
            "elapsed_s": elapsed,
            "power_w": np.nan,
            "hr": np.nan,
            "cadence": np.nan,
            "altitude_m": np.nan,
            "lat": None,
            "lon": None,
            "speed_kmh": np.nan,
        }

        # Position
        pos = tp.find("tcx:Position", NS)
        if pos is not None:
            lat_el = pos.find("tcx:LatitudeDegrees", NS)
            lon_el = pos.find("tcx:LongitudeDegrees", NS)
            if lat_el is not None and lat_el.text:
                row["lat"] = float(lat_el.text)
            if lon_el is not None and lon_el.text:
                row["lon"] = float(lon_el.text)

        # Altitude
        alt_el = tp.find("tcx:AltitudeMeters", NS)
        if alt_el is not None and alt_el.text:
            row["altitude_m"] = float(alt_el.text)

        # FC
        hr_el = tp.find("tcx:HeartRateBpm/tcx:Value", NS)
        if hr_el is not None and hr_el.text:
            row["hr"] = float(hr_el.text)

        # Cadence (dans le trackpoint principal)
        cad_el = tp.find("tcx:Cadence", NS)
        if cad_el is not None and cad_el.text:
            row["cadence"] = float(cad_el.text)

        # Extensions (puissance, cadence alternative)
        for ext_el in tp.findall(".//ext:Watts", NS):
            if ext_el.text:
                row["power_w"] = float(ext_el.text)
        # Cadence dans les extensions
        for ext_el in tp.findall(".//ext:RunCadence", NS):
            if ext_el.text and np.isnan(row["cadence"]):
                row["cadence"] = float(ext_el.text)

        # Vitesse via extensions
        for ext_el in tp.findall(".//ext:Speed", NS):
            if ext_el.text:
                row["speed_kmh"] = float(ext_el.text) * 3.6

        rows.append(row)

    if not rows:
        return _empty_df()

    df = pd.DataFrame(rows)
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[EXPECTED_COLUMNS]


# ─────────────────────────── Dispatcher ───────────────────────────

def parse_file(filename: str, file_bytes: bytes) -> pd.DataFrame:
    """Dispatcher : détecte le format et appelle le bon parser."""
    ext = Path(filename).suffix.lower()
    if ext == ".fit":
        return parse_fit(file_bytes)
    elif ext == ".gpx":
        return parse_gpx(file_bytes)
    elif ext == ".tcx":
        return parse_tcx(file_bytes)
    else:
        log.warning("Format non supporté : %s", ext)
        return _empty_df()


def extract_summary_from_df(df: pd.DataFrame, filename: str) -> dict:
    """Extrait un résumé (compatible db.upsert_activity) depuis un DataFrame parsé.

    Utilisé pour créer une entrée d'activité à partir d'un fichier importé.
    """
    if df.empty:
        return {}

    duration_s = df["elapsed_s"].max() - df["elapsed_s"].min()

    # Distance via intégration de la vitesse ou GPS
    distance_m = None
    if df["speed_kmh"].notna().any():
        dt_s = df["elapsed_s"].diff().fillna(1).clip(lower=0, upper=10)
        distance_m = (df["speed_kmh"].fillna(0) / 3.6 * dt_s).sum()
    elif df["lat"].notna().any() and df["lon"].notna().any():
        distance_m = _haversine_distance(df)

    # Dénivelé
    elevation_gain = None
    if df["altitude_m"].notna().any():
        alt = df["altitude_m"].dropna()
        diffs = alt.diff().dropna()
        elevation_gain = float(diffs[diffs > 0].sum())

    # Vitesse moyenne
    avg_speed = None
    if df["speed_kmh"].notna().any():
        avg_speed = float(df["speed_kmh"].mean())

    return {
        "start_time": "",  # sera rempli si on a un timestamp
        "name": Path(filename).stem,
        "activity_type": "cycling",
        "distance_m": distance_m,
        "duration_s": duration_s,
        "elevation_gain_m": elevation_gain,
        "avg_speed_kmh": avg_speed,
        "max_speed_kmh": float(df["speed_kmh"].max()) if df["speed_kmh"].notna().any() else None,
        "avg_power_w": float(df["power_w"].mean()) if df["power_w"].notna().any() else None,
        "max_power_w": float(df["power_w"].max()) if df["power_w"].notna().any() else None,
        "avg_hr": float(df["hr"].mean()) if df["hr"].notna().any() else None,
        "max_hr": float(df["hr"].max()) if df["hr"].notna().any() else None,
        "calories": None,
        "training_load": None,
        "source": "file_import",
        "raw_json": None,
    }


def _haversine_distance(df: pd.DataFrame) -> float:
    """Calcule la distance totale en mètres via la formule de Haversine."""
    lats = df["lat"].dropna().values
    lons = df["lon"].dropna().values
    if len(lats) < 2:
        return 0.0

    R = 6_371_000  # rayon de la Terre en mètres
    lat1 = np.radians(lats[:-1])
    lat2 = np.radians(lats[1:])
    dlat = lat2 - lat1
    dlon = np.radians(lons[1:]) - np.radians(lons[:-1])

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return float(np.sum(2 * R * np.arcsin(np.sqrt(a))))
