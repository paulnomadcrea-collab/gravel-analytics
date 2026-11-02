"""
Moteur d'analyse : zones de puissance, charge d'entraînement, progression.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Zones de puissance façon Coggan (% de la FTP), modifiables dans l'appli.
DEFAULT_ZONES = [
    ("Z1 Récupération", 0.00, 0.55),
    ("Z2 Endurance", 0.55, 0.75),
    ("Z3 Tempo", 0.75, 0.90),
    ("Z4 Seuil", 0.90, 1.05),
    ("Z5 VO2max", 1.05, 1.20),
    ("Z6 Anaérobie", 1.20, 1.50),
    ("Z7 Neuromusculaire", 1.50, 99.0),
]


def zone_bounds_watts(ftp: float, zones=DEFAULT_ZONES) -> list[tuple[str, float, float]]:
    return [(name, lo * ftp, hi * ftp) for name, lo, hi in zones]


def parse_power_stream(activity_detail: dict) -> pd.DataFrame:
    """Extrait la série temporelle puissance/FC/vitesse d'un détail d'activité
    Garmin Connect (format `activityDetailMetrics`)."""
    metrics = activity_detail.get("activityDetailMetrics")
    descriptors = activity_detail.get("metricDescriptors")
    if not metrics or not descriptors:
        return pd.DataFrame(columns=["elapsed_s", "power_w", "hr", "speed_kmh", "altitude_m"])

    key_map = {d["key"]: d["metricsIndex"] for d in descriptors}

    def col(key, default=np.nan):
        idx = key_map.get(key)
        if idx is None:
            return [default] * len(metrics)
        return [m["metrics"][idx] if m.get("metrics") and len(m["metrics"]) > idx else default for m in metrics]

    df = pd.DataFrame(
        {
            "elapsed_s": col("sumDuration", np.nan),
            "power_w": col("directPower", np.nan),
            "hr": col("directHeartRate", np.nan),
            "speed_kmh": [v * 3.6 if v is not None else np.nan for v in col("directSpeed", np.nan)],
            "altitude_m": col("directElevation", np.nan),
        }
    )
    return df.dropna(subset=["elapsed_s"])


def time_and_avg_power_per_zone(power_df: pd.DataFrame, ftp: float, zones=DEFAULT_ZONES) -> pd.DataFrame:
    """Pour chaque zone : temps passé (s) et puissance moyenne *pendant* les
    portions de la sortie passées dans cette zone — c'est cette dernière
    valeur pour la zone 2 qui correspond à l'objectif de progression (220W -> 260W)."""
    bounds = zone_bounds_watts(ftp, zones)
    rows = []
    p = power_df["power_w"].dropna()
    dt_s = power_df["elapsed_s"].diff().fillna(1).clip(lower=0, upper=10)
    for name, lo, hi in bounds:
        mask = (power_df["power_w"] >= lo) & (power_df["power_w"] < hi)
        time_s = dt_s[mask].sum()
        avg_p = power_df.loc[mask, "power_w"].mean()
        rows.append({"zone": name, "time_s": time_s, "avg_power_w": avg_p})
    return pd.DataFrame(rows)


def normalized_power(power_df: pd.DataFrame) -> float:
    """NP façon Coggan : moyenne mobile 30s^4, puis racine 4e, moyenne."""
    p = power_df["power_w"].fillna(0)
    if len(p) < 30:
        return float(p.mean()) if len(p) else float("nan")
    rolling = p.rolling(30, min_periods=1).mean()
    return float((rolling**4).mean() ** 0.25)


def training_stress_score(np_watts: float, ftp: float, duration_s: float) -> float:
    if not ftp or np_watts != np_watts:  # NaN check
        return float("nan")
    intensity_factor = np_watts / ftp
    return (duration_s * np_watts * intensity_factor) / (ftp * 3600) * 100


@dataclass
class PmcPoint:
    date: dt.date
    tss: float
    ctl: float  # fitness (42j)
    atl: float  # fatigue (7j)
    tsb: float  # forme = ctl - atl


def performance_management_chart(daily_tss: pd.Series) -> pd.DataFrame:
    """Calcule CTL (fitness, moy. mobile exp. 42j), ATL (fatigue, 7j) et
    TSB (forme = CTL - ATL) à partir d'une série de TSS quotidien (index = date)."""
    idx = pd.date_range(daily_tss.index.min(), daily_tss.index.max(), freq="D")
    s = daily_tss.reindex(idx, fill_value=0)
    ctl = s.ewm(span=42, adjust=False).mean()
    atl = s.ewm(span=7, adjust=False).mean()
    tsb = ctl - atl
    return pd.DataFrame({"date": idx, "tss": s.values, "ctl": ctl.values, "atl": atl.values, "tsb": tsb.values})


def intensity_factor(np_watts: float, ftp: float) -> float:
    """IF = NP / FTP. Mesure l'intensité relative d'une sortie."""
    if not ftp or np_watts != np_watts:
        return float("nan")
    return np_watts / ftp


def best_efforts(power_df: pd.DataFrame, durations: list[int] | None = None) -> dict[int, float]:
    """Calcule la meilleure puissance moyenne soutenue pour chaque durée (en secondes).

    Retourne {durée_s: meilleur_watts}. Les durées par défaut couvrent
    le spectre classique : 5s, 30s, 1min, 5min, 10min, 20min, 60min.
    """
    if durations is None:
        durations = [5, 30, 60, 300, 600, 1200, 3600]

    p = power_df["power_w"].fillna(0).values
    n = len(p)
    results = {}
    for dur in durations:
        if n < dur:
            results[dur] = float("nan")
            continue
        # Rolling mean via cumsum pour performance
        cumsum = np.concatenate(([0], np.cumsum(p)))
        rolling_avg = (cumsum[dur:] - cumsum[:-dur]) / dur
        results[dur] = float(np.max(rolling_avg)) if len(rolling_avg) > 0 else float("nan")
    return results


def difficulty_score(
    distance_m: float | None,
    elevation_gain_m: float | None,
    duration_s: float | None,
    avg_power_w: float | None,
    ftp: float = 250.0,
) -> float | None:
    """Score de difficulté composite (0–100) pour une sortie gravel/vélo.

    Combine : distance, dénivelé, intensité (puissance/FTP), durée.
    Pondération orientée gravel (le dénivelé pèse lourd).
    """
    if duration_s is None or duration_s <= 0:
        return None

    score = 0.0

    # Composante distance (max 25 pts — 100km = 25 pts)
    if distance_m and distance_m > 0:
        score += min(25.0, (distance_m / 1000) / 100 * 25)

    # Composante dénivelé (max 30 pts — 2000m D+ = 30 pts)
    if elevation_gain_m and elevation_gain_m > 0:
        score += min(30.0, elevation_gain_m / 2000 * 30)

    # Composante intensité (max 25 pts — IF=1.0 = 25 pts)
    if avg_power_w and ftp and ftp > 0:
        if_val = avg_power_w / ftp
        score += min(25.0, if_val / 1.0 * 25)

    # Composante durée (max 20 pts — 5h = 20 pts)
    duration_h = duration_s / 3600
    score += min(20.0, duration_h / 5.0 * 20)

    return round(min(100.0, score), 1)


def z2_progress(activities_df: pd.DataFrame, goal_w: float = 260.0, baseline_w: float = 220.0) -> dict:
    """Résumé de la progression vers l'objectif puissance moyenne en Z2."""
    if activities_df.empty or "avg_z2_power_w" not in activities_df:
        return {"current": None, "goal": goal_w, "baseline": baseline_w, "pct_to_goal": None}
    recent = activities_df.dropna(subset=["avg_z2_power_w"]).tail(5)
    current = float(recent["avg_z2_power_w"].mean()) if not recent.empty else None
    pct = None
    if current is not None and goal_w > baseline_w:
        pct = max(0.0, min(1.0, (current - baseline_w) / (goal_w - baseline_w)))
    return {"current": current, "goal": goal_w, "baseline": baseline_w, "pct_to_goal": pct}
