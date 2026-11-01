"""
Coach IA — analyse automatique des dernières sorties et recommandations
personnalisées incluant entraînement, nutrition et hydratation.

Moteur basé sur des règles issues de la littérature sport-endurance :
- Charge d'entraînement (Banister, Coggan)
- Nutrition sportive (Jeukendrup, ACSM guidelines)
- Hydratation (ACSM Position Stand 2007, Sawka et al.)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from analysis import (
    DEFAULT_ZONES,
    performance_management_chart,
    zone_bounds_watts,
)


# ──────────────────────────── Data classes ────────────────────────────

@dataclass
class RideSummary:
    """Résumé d'une sortie individuelle pour le coach."""
    date: dt.date
    name: str
    duration_h: float
    distance_km: float
    elevation_m: float
    avg_power_w: float | None
    normalized_power_w: float | None
    avg_hr: int | None
    tss: float | None
    avg_z2_power_w: float | None
    calories: float | None
    intensity_factor: float | None  # NP / FTP


@dataclass
class NutritionAdvice:
    """Recommandations nutrition/hydratation pour une sortie type."""
    duration_category: str  # "courte", "moyenne", "longue", "ultra"
    carbs_per_hour_g: tuple[int, int]  # fourchette min-max
    water_per_hour_ml: tuple[int, int]
    electrolytes_mg_sodium_h: tuple[int, int]
    pre_ride_meal: str
    during_ride: list[str]
    post_ride: str
    notes: list[str]


@dataclass
class CoachReport:
    """Rapport complet du coach IA."""
    generated_at: dt.datetime
    period_days: int
    rides_analyzed: int

    # État de forme
    fitness_status: str  # "En forme", "Fatigué", "Surentraîné", "Frais"
    fitness_emoji: str
    fitness_detail: str
    ctl: float | None
    atl: float | None
    tsb: float | None

    # Volume & régularité
    weekly_hours_avg: float
    weekly_km_avg: float
    weekly_elevation_avg: float
    rides_per_week_avg: float
    consistency_score: int  # 0-100
    consistency_comment: str

    # Tendances de performance
    power_trend: str | None  # "↗ En progression", "→ Stable", "↘ En baisse"
    speed_trend: str | None
    hr_trend: str | None
    trend_details: list[str]

    # Distribution des zones
    zone_distribution: dict[str, float] | None  # zone_name -> % du temps
    zone_comment: str | None

    # Recommandations entraînement
    training_recommendations: list[str]

    # Nutrition & hydratation
    nutrition_advice: NutritionAdvice
    ride_specific_nutrition: list[dict]  # par sortie récente

    # Score global et résumé
    overall_score: int  # 0-100
    summary: str


# ──────────────────────────── Helpers ────────────────────────────

def _trend_label(values: list[float], unit: str = "") -> tuple[str, str]:
    """Calcule la tendance sur une série de valeurs récentes."""
    if len(values) < 4:
        return "→ Stable", f"Pas assez de données pour une tendance fiable ({len(values)} sorties)"

    first_half = np.mean(values[: len(values) // 2])
    second_half = np.mean(values[len(values) // 2 :])

    if first_half == 0:
        return "→ Stable", "Valeurs nulles"

    pct_change = (second_half - first_half) / first_half * 100

    if pct_change > 3:
        return "↗ En progression", f"+{pct_change:.1f}% ({first_half:.0f} → {second_half:.0f} {unit})"
    elif pct_change < -3:
        return "↘ En baisse", f"{pct_change:.1f}% ({first_half:.0f} → {second_half:.0f} {unit})"
    else:
        return "→ Stable", f"Variation de {pct_change:+.1f}% — dans la norme"


def _consistency_score(dates: list[dt.date], period_days: int) -> tuple[int, str]:
    """Score de régularité basé sur la distribution des sorties dans la semaine."""
    if len(dates) < 2:
        return 0, "Pas assez de sorties pour évaluer la régularité"

    # Compter les semaines avec au moins 1 sortie
    weeks = set()
    for d in dates:
        weeks.add(d.isocalendar()[:2])

    total_weeks = max(1, period_days / 7)
    active_weeks_pct = len(weeks) / total_weeks * 100

    # Score basé sur la régularité inter-sorties
    gaps = sorted([(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)])
    median_gap = np.median(gaps)
    gap_std = np.std(gaps)

    # Score : régularité (peu de variance) + fréquence
    regularity = max(0, 100 - gap_std * 10)
    frequency = min(100, active_weeks_pct * 1.2)
    score = int(min(100, (regularity * 0.5 + frequency * 0.5)))

    if score >= 80:
        comment = "Excellente régularité — tu roules de manière très constante"
    elif score >= 60:
        comment = "Bonne régularité — quelques semaines creuses mais rien d'alarmant"
    elif score >= 40:
        comment = f"Régularité moyenne — écart médian de {median_gap:.0f} jours entre sorties"
    else:
        comment = "Régularité faible — essaie de rouler au moins 2-3 fois par semaine"

    return score, comment


def _fitness_assessment(tsb: float | None, ctl: float | None, atl: float | None) -> tuple[str, str, str]:
    """Évalue l'état de forme à partir du TSB."""
    if tsb is None:
        return "Inconnu", "❓", "Données de puissance insuffisantes pour évaluer la forme"

    if tsb > 15:
        return "Frais & reposé", "🟢", (
            f"TSB à {tsb:+.0f} — tu es bien reposé. "
            "C'est le moment idéal pour une sortie intense ou un objectif."
        )
    elif tsb > 0:
        return "En forme", "🟢", (
            f"TSB à {tsb:+.0f} — bon équilibre entre charge et récupération. "
            "Continue comme ça."
        )
    elif tsb > -15:
        return "Charge modérée", "🟡", (
            f"TSB à {tsb:+.0f} — charge d'entraînement en cours, fatigue normale. "
            "Assure-toi de bien récupérer."
        )
    elif tsb > -30:
        return "Fatigué", "🟠", (
            f"TSB à {tsb:+.0f} — accumulation de fatigue significative. "
            "Privilégie les sorties Z2 et la récupération active pendant 3-5 jours."
        )
    else:
        return "Surentraîné", "🔴", (
            f"TSB à {tsb:+.0f} — risque de surentraînement. "
            "Réduis le volume de 30-50% cette semaine. Sommeil, nutrition et repos sont prioritaires."
        )


def _zone_analysis(zone_dist: dict[str, float] | None) -> str | None:
    """Commentaire sur la distribution des zones de puissance."""
    if not zone_dist:
        return None

    z2_pct = zone_dist.get("Z2 Endurance", 0)
    z1_pct = zone_dist.get("Z1 Récupération", 0)
    high_zones_pct = sum(v for k, v in zone_dist.items() if k.startswith(("Z4", "Z5", "Z6", "Z7")))

    comments = []
    if z2_pct >= 60:
        comments.append("✅ Excellente polarisation — majorité du temps en Z2 (endurance fondamentale)")
    elif z2_pct >= 40:
        comments.append("👍 Bonne base Z2, mais tu pourrais augmenter le temps en endurance")
    else:
        comments.append(
            f"⚠️ Seulement {z2_pct:.0f}% en Z2 — vise 65-80% de ton temps en endurance. "
            "L'aérobie se construit en Z2."
        )

    if high_zones_pct > 25:
        comments.append(
            f"⚠️ {high_zones_pct:.0f}% du temps en haute intensité — risque de fatigue chronique. "
            "Règle 80/20 : 80% facile, 20% intense."
        )
    elif high_zones_pct < 5 and z2_pct > 0:
        comments.append(
            "💡 Très peu de haute intensité — ajoute 1-2 sessions de fractionné par semaine "
            "pour progresser en VO2max."
        )

    return " · ".join(comments)


# ──────────────────────────── Nutrition engine ────────────────────────────

def _nutrition_for_duration(duration_h: float, avg_power_w: float | None, weight_kg: float = 75) -> NutritionAdvice:
    """Recommandations nutrition/hydratation basées sur la durée et l'intensité.

    Sources :
    - Jeukendrup A. (2014) — A Step Towards Personalized Sports Nutrition
    - ACSM Position Stand on Exercise and Fluid Replacement (2007)
    - Thomas et al. (2016) — Nutrition and Athletic Performance
    """
    # Estimation des besoins caloriques
    if avg_power_w:
        # Calories ≈ kJ (power × time) / 0.25 (rendement ~25%)
        estimated_kcal_h = avg_power_w * 3.6 / 0.25  # kJ/h → kcal/h ajusté
        # Simplification : kJ ≈ kcal × 4.184, rendement mécanique ~25%
        estimated_kcal_h = avg_power_w * 3600 / 1000 / 0.25  # plus précis
    else:
        estimated_kcal_h = 600  # estimation conservatrice pour vélo

    if duration_h < 1.5:
        return NutritionAdvice(
            duration_category="courte (< 1h30)",
            carbs_per_hour_g=(0, 30),
            water_per_hour_ml=(400, 600),
            electrolytes_mg_sodium_h=(200, 400),
            pre_ride_meal="Repas normal 2-3h avant ou collation légère 1h avant (banane, barre de céréales)",
            during_ride=[
                "Eau seule suffit pour les sorties < 1h",
                "Une boisson isotonique légère pour 1h-1h30",
                "Pas besoin de gel ou barre si tu as bien mangé avant",
            ],
            post_ride="Collation protéines + glucides dans les 30 min (yaourt + fruit, ou lait chocolaté)",
            notes=["Les réserves de glycogène couvrent ~90 min d'effort modéré"],
        )
    elif duration_h < 3:
        return NutritionAdvice(
            duration_category="moyenne (1h30 – 3h)",
            carbs_per_hour_g=(30, 60),
            water_per_hour_ml=(500, 750),
            electrolytes_mg_sodium_h=(300, 600),
            pre_ride_meal="Petit-déjeuner riche en glucides 2-3h avant (flocons d'avoine, pain, confiture, banane)",
            during_ride=[
                "30-60g de glucides/heure dès la 1re heure",
                "Alterner entre boisson isotonique et gels/barres",
                "Exemples : 1 gel (25g) + 500ml boisson iso (30g) = ~55g/h",
                "Boire régulièrement (150-200ml toutes les 15-20 min)",
            ],
            post_ride=(
                "Repas complet dans l'heure : glucides (pâtes, riz) + protéines (poulet, œufs, légumineuses) "
                "+ légumes. Viser 1-1.2g glucides/kg et 20-30g protéines."
            ),
            notes=[
                "Entraîne ton intestin à absorber des glucides à l'effort",
                "La soif n'est pas un bon indicateur — bois à intervalles réguliers",
            ],
        )
    elif duration_h < 5:
        return NutritionAdvice(
            duration_category="longue (3h – 5h)",
            carbs_per_hour_g=(60, 90),
            water_per_hour_ml=(500, 800),
            electrolytes_mg_sodium_h=(400, 800),
            pre_ride_meal=(
                "Repas copieux 3h avant (porridge, pain complet, beurre de cacahuète, banane). "
                "Ajouter une collation 1h avant si besoin."
            ),
            during_ride=[
                "60-90g de glucides/heure — indispensable pour éviter le mur",
                "Mélange glucose + fructose (ratio 2:1) pour absorber > 60g/h",
                "Exemple : 1 gel (25g) + 1 barre (30g) + 750ml boisson iso (45g) = ~100g/h",
                "Alterner sucré/salé pour éviter l'écœurement",
                "Boire 150-200ml toutes les 15 min, ajuster si chaud",
                "Ajouter du sel dans la boisson (1-1.5g/L) ou pastilles d'électrolytes",
            ],
            post_ride=(
                "Récupération en 2 phases : boisson de récupération immédiate (glucides + protéines), "
                "puis repas complet dans les 2h. Priorité à la réhydratation : 1.5× le poids perdu."
            ),
            notes=[
                "Commence à manger dès les 30 premières minutes",
                "Prévois +20% de provisions par rapport à tes besoins calculés",
                "Pèse-toi avant/après pour estimer tes pertes hydriques",
            ],
        )
    else:
        return NutritionAdvice(
            duration_category="ultra (> 5h)",
            carbs_per_hour_g=(80, 120),
            water_per_hour_ml=(600, 1000),
            electrolytes_mg_sodium_h=(500, 1000),
            pre_ride_meal=(
                "Carb-loading la veille (8-10g glucides/kg). Petit-déjeuner copieux 3h avant "
                "(riz, flocons, pain blanc, miel, jus de fruit)."
            ),
            during_ride=[
                "80-120g de glucides/heure — l'alimentation EST la performance",
                "Mélange multi-transporteurs (glucose + fructose + maltodextrine)",
                "Variété obligatoire : gels, barres, riz sucré, bananes, boisson",
                "Boire toutes les 10-15 min, ne jamais attendre la soif",
                "Électrolytes renforcés : 500-1000mg sodium/h selon la chaleur",
                "Prévoir des aliments salés (bretzel, sandwich) au-delà de 4h",
                "Caféine (3-6mg/kg) après mi-parcours si besoin de boost mental",
            ],
            post_ride=(
                "Réhydratation immédiate (boisson de récup), repas copieux dès que possible. "
                "Les 24h suivantes : manger à satiété, dormir 8-9h, éviter l'alcool."
            ),
            notes=[
                "L'entraînement digestif est aussi important que l'entraînement physique",
                "Teste ta stratégie nutritionnelle en entraînement, jamais le jour J",
                "Surveille la couleur de tes urines comme indicateur d'hydratation",
            ],
        )


def _ride_nutrition_summary(ride: RideSummary, ftp: float) -> dict:
    """Génère un résumé nutrition spécifique à une sortie passée."""
    intensity = "modérée"
    if ride.intensity_factor and ride.intensity_factor > 0.85:
        intensity = "élevée"
    elif ride.intensity_factor and ride.intensity_factor < 0.65:
        intensity = "basse"

    # Estimation des besoins en glucides sur cette sortie
    advice = _nutrition_for_duration(ride.duration_h, ride.avg_power_w)
    carb_min = advice.carbs_per_hour_g[0] * ride.duration_h
    carb_max = advice.carbs_per_hour_g[1] * ride.duration_h
    water_min = advice.water_per_hour_ml[0] * ride.duration_h / 1000
    water_max = advice.water_per_hour_ml[1] * ride.duration_h / 1000

    # Calories brûlées estimées
    import math
    if ride.avg_power_w and not math.isnan(ride.avg_power_w):
        calories_estimated = ride.avg_power_w * (ride.duration_h or 0) * 3600 / 1000 / 0.25
    elif ride.calories and not math.isnan(ride.calories):
        calories_estimated = ride.calories
    else:
        calories_estimated = (ride.duration_h or 0) * 600

    # Sécuriser contre NaN/None avant conversion en int
    def _safe_int(v, default=0):
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return default
            return int(v)
        except (ValueError, TypeError):
            return default

    return {
        "date": ride.date.strftime("%d/%m/%Y"),
        "name": ride.name,
        "duration_h": ride.duration_h,
        "intensity": intensity,
        "calories_estimated": _safe_int(calories_estimated),
        "carbs_needed_g": f"{_safe_int(carb_min)}–{_safe_int(carb_max)}",
        "water_needed_l": f"{water_min:.1f}–{water_max:.1f}" if water_min == water_min and water_max == water_max else "0.0–0.0",
        "category": advice.duration_category,
    }


# ──────────────────────────── Training recommendations ────────────────────────────

def _training_recommendations(
    tsb: float | None,
    ctl: float | None,
    weekly_hours: float,
    rides_per_week: float,
    zone_dist: dict[str, float] | None,
    power_trend: str | None,
) -> list[str]:
    """Génère les recommandations d'entraînement personnalisées."""
    recs = []

    # Basé sur TSB
    if tsb is not None:
        if tsb < -25:
            recs.append(
                "🛑 **Semaine de récupération nécessaire** — réduis le volume de 40-50% : "
                "2-3 sorties courtes en Z1/Z2, pas d'intervalles."
            )
        elif tsb < -10:
            recs.append(
                "⚡ **Charge élevée** — continue de construire mais ajoute un jour de repos "
                "complet si tu sens la fatigue s'installer."
            )
        elif tsb > 20:
            recs.append(
                "🚀 **Tu es frais** — c'est le moment de placer un bloc intense : "
                "intervalles Z4/Z5 ou une grosse sortie longue."
            )

    # Basé sur le volume
    if weekly_hours < 3:
        recs.append(
            "📈 **Volume faible** — vise 4-6h/semaine minimum pour progresser en endurance. "
            "Ajoute une sortie Z2 de 1.5-2h le week-end."
        )
    elif weekly_hours > 12:
        recs.append(
            "⚠️ **Volume très élevé** — assure-toi d'avoir au minimum 1-2 jours de repos complets "
            "par semaine et une semaine allégée toutes les 3-4 semaines."
        )

    # Basé sur la fréquence
    if rides_per_week < 2:
        recs.append(
            "📅 **Fréquence insuffisante** — 3 sorties/semaine est le minimum pour progresser. "
            "Même 45 min en Z2 compte."
        )

    # Basé sur les zones
    if zone_dist:
        z2_pct = zone_dist.get("Z2 Endurance", 0)
        z3_pct = zone_dist.get("Z3 Tempo", 0)

        if z3_pct > 30:
            recs.append(
                "🎯 **Trop de Z3 (tempo/no man's land)** — le Z3 fatigue sans les bénéfices "
                "du Z2 (base aérobie) ni du Z4+ (VO2max). Polarise : facile OU intense."
            )
        if z2_pct < 50 and weekly_hours > 3:
            recs.append(
                "🔄 **Manque de base aérobie** — augmente le temps en Z2. Les pros passent "
                "75-80% de leur temps en endurance fondamentale."
            )

    # Basé sur la tendance de puissance
    if power_trend and "En baisse" in power_trend:
        recs.append(
            "💡 **Puissance en baisse** — cela peut indiquer de la fatigue accumulée ou un manque "
            "de stimulation haute intensité. Analyse ta récupération et ton sommeil."
        )

    # Recommandation par défaut si tout va bien
    if not recs:
        recs.append(
            "✅ **Bon travail !** — tes paramètres sont dans les clous. Continue sur cette lancée "
            "et n'oublie pas la règle des 10% max d'augmentation de volume par semaine."
        )

    return recs


# ──────────────────────────── Main entry point ────────────────────────────

def generate_coach_report(
    df: pd.DataFrame,
    ftp: float = 260,
    period_days: int = 28,
    weight_kg: float = 75,
) -> CoachReport | None:
    """Génère un rapport de coaching complet basé sur les activités récentes.

    Args:
        df: DataFrame des activités (depuis db.load_activities_df())
        ftp: FTP actuelle du coureur
        period_days: Nombre de jours à analyser
        weight_kg: Poids du coureur (pour les calculs nutrition)

    Returns:
        CoachReport ou None si pas assez de données
    """
    if df.empty:
        return None

    # Filtrer sur la période
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=period_days)
    recent = df[df["start_time"] >= cutoff].copy()

    if recent.empty:
        return None

    # ── Construire les résumés par sortie ──
    rides = []
    for _, row in recent.iterrows():
        duration_h = (row["duration_s"] or 0) / 3600
        np_w = row.get("normalized_power_w")
        if_val = np_w / ftp if np_w and ftp else None

        rides.append(RideSummary(
            date=row["start_time"].date(),
            name=row.get("name", ""),
            duration_h=duration_h,
            distance_km=(row["distance_m"] or 0) / 1000,
            elevation_m=row.get("elevation_gain_m") or 0,
            avg_power_w=row.get("avg_power_w"),
            normalized_power_w=np_w,
            avg_hr=row.get("avg_hr"),
            tss=row.get("tss"),
            avg_z2_power_w=row.get("avg_z2_power_w"),
            calories=row.get("calories"),
            intensity_factor=if_val,
        ))

    # ── Volume & régularité ──
    weeks_in_period = max(1, period_days / 7)
    total_hours = sum(r.duration_h for r in rides)
    total_km = sum(r.distance_km for r in rides)
    total_elevation = sum(r.elevation_m for r in rides)
    weekly_hours = total_hours / weeks_in_period
    weekly_km = total_km / weeks_in_period
    weekly_elevation = total_elevation / weeks_in_period
    rides_per_week = len(rides) / weeks_in_period

    dates = sorted([r.date for r in rides])
    consistency, consistency_comment = _consistency_score(dates, period_days)

    # ── Tendances ──
    sorted_rides = sorted(rides, key=lambda r: r.date)

    # Power trend
    power_values = [r.avg_power_w for r in sorted_rides if r.avg_power_w]
    power_trend, power_detail = _trend_label(power_values, "W") if power_values else ("→ Stable", "Pas de données de puissance")

    # Speed trend
    speed_values = [r.distance_km / r.duration_h for r in sorted_rides if r.duration_h > 0]
    speed_trend, speed_detail = _trend_label(speed_values, "km/h") if speed_values else ("→ Stable", "")

    # HR trend
    hr_values = [r.avg_hr for r in sorted_rides if r.avg_hr]
    hr_trend, hr_detail = _trend_label(hr_values, "bpm") if hr_values else (None, "")

    trend_details = []
    if power_values:
        trend_details.append(f"**Puissance** : {power_trend} — {power_detail}")
    if speed_values:
        trend_details.append(f"**Vitesse** : {speed_trend} — {speed_detail}")
    if hr_values:
        trend_details.append(f"**FC moyenne** : {hr_trend} — {hr_detail}")
        # Découplage aérobie : si la FC monte et la puissance stagne → fatigue
        if hr_trend and "progression" in hr_trend.lower() and power_trend and "baisse" in power_trend.lower():
            trend_details.append(
                "⚠️ **Découplage FC/Puissance** — ta FC augmente pendant que ta puissance baisse. "
                "Signe possible de fatigue ou de déshydratation chronique."
            )

    # ── Distribution des zones ──
    zone_dist = None
    zone_comment = None
    tss_series = recent.dropna(subset=["tss"])

    # Calculer la distribution des zones à partir des données disponibles
    # On utilise avg_power_w par rapport aux zones FTP comme approximation
    if not recent["avg_power_w"].dropna().empty:
        bounds = zone_bounds_watts(ftp)
        zone_times = {}
        for _, row in recent.iterrows():
            pw = row.get("avg_power_w")
            dur = row.get("duration_s") or 0
            if pw and dur:
                for zname, lo, hi in bounds:
                    short_name = zname.split(" ")[0] + " " + " ".join(zname.split(" ")[1:])
                    if lo <= pw < hi:
                        zone_times[short_name] = zone_times.get(short_name, 0) + dur
                        break

        total_zone_time = sum(zone_times.values())
        if total_zone_time > 0:
            zone_dist = {k: v / total_zone_time * 100 for k, v in zone_times.items()}
            zone_comment = _zone_analysis(zone_dist)

    # ── Charge d'entraînement (CTL / ATL / TSB) ──
    ctl_val, atl_val, tsb_val = None, None, None
    if not tss_series.empty:
        daily = tss_series.set_index(tss_series["start_time"].dt.normalize())["tss"].groupby(level=0).sum()
        if len(daily) >= 2:
            pmc = performance_management_chart(daily)
            if not pmc.empty:
                ctl_val = float(pmc["ctl"].iloc[-1])
                atl_val = float(pmc["atl"].iloc[-1])
                tsb_val = float(pmc["tsb"].iloc[-1])

    fitness_status, fitness_emoji, fitness_detail = _fitness_assessment(tsb_val, ctl_val, atl_val)

    # ── Nutrition ──
    # Nutrition type basée sur la durée moyenne des sorties récentes
    avg_duration = np.mean([r.duration_h for r in rides])
    avg_power = np.nanmean([r.avg_power_w for r in rides if r.avg_power_w]) if any(r.avg_power_w for r in rides) else None
    nutrition_advice = _nutrition_for_duration(avg_duration, avg_power, weight_kg)

    # Nutrition spécifique aux 5 dernières sorties
    recent_5 = sorted_rides[-5:]
    ride_specific_nutrition = [_ride_nutrition_summary(r, ftp) for r in recent_5]

    # ── Recommandations ──
    training_recs = _training_recommendations(
        tsb_val, ctl_val, weekly_hours, rides_per_week, zone_dist, power_trend
    )

    # ── Score global ──
    score_components = []
    score_components.append(min(30, consistency * 0.3))  # max 30 pts
    score_components.append(min(20, rides_per_week * 5))  # max 20 pts (4+ rides/week)
    score_components.append(min(20, weekly_hours * 3.3))  # max 20 pts (6h/week)
    if tsb_val is not None:
        # TSB entre -10 et +10 = optimal
        tsb_score = max(0, 15 - abs(tsb_val) * 0.5)
        score_components.append(min(15, tsb_score))
    else:
        score_components.append(7)  # neutre
    if zone_dist and zone_dist.get("Z2 Endurance", 0) > 50:
        score_components.append(15)
    elif zone_dist:
        score_components.append(max(0, zone_dist.get("Z2 Endurance", 0) * 0.3))
    else:
        score_components.append(7)

    overall_score = int(min(100, sum(score_components)))

    # ── Résumé ──
    summary_parts = []
    summary_parts.append(f"Sur les {period_days} derniers jours : {len(rides)} sorties, "
                          f"{total_hours:.0f}h de vélo, {total_km:.0f} km.")
    summary_parts.append(f"État de forme : {fitness_status}.")
    if power_trend and power_values:
        summary_parts.append(f"Tendance puissance : {power_trend}.")
    summary_parts.append(
        f"Pour tes sorties de ~{avg_duration:.1f}h, prévois {nutrition_advice.carbs_per_hour_g[0]}-"
        f"{nutrition_advice.carbs_per_hour_g[1]}g de glucides/h et "
        f"{nutrition_advice.water_per_hour_ml[0]}-{nutrition_advice.water_per_hour_ml[1]}ml d'eau/h."
    )

    return CoachReport(
        generated_at=dt.datetime.now(),
        period_days=period_days,
        rides_analyzed=len(rides),
        fitness_status=fitness_status,
        fitness_emoji=fitness_emoji,
        fitness_detail=fitness_detail,
        ctl=ctl_val,
        atl=atl_val,
        tsb=tsb_val,
        weekly_hours_avg=weekly_hours,
        weekly_km_avg=weekly_km,
        weekly_elevation_avg=weekly_elevation,
        rides_per_week_avg=rides_per_week,
        consistency_score=consistency,
        consistency_comment=consistency_comment,
        power_trend=power_trend,
        speed_trend=speed_trend,
        hr_trend=hr_trend,
        trend_details=trend_details,
        zone_distribution=zone_dist,
        zone_comment=zone_comment,
        training_recommendations=training_recs,
        nutrition_advice=nutrition_advice,
        ride_specific_nutrition=ride_specific_nutrition,
        overall_score=overall_score,
        summary=" ".join(summary_parts),
    )
