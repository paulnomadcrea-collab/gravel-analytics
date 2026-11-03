"""
Gravel Coach V2 — Demo / fallback data.

Used when the database is empty (no synced activities yet).
Provides realistic preview data so the UI is never blank.
"""
from __future__ import annotations

import datetime as dt

DEMO_ACTIVITIES = [
    {"id": "d1", "date": "2 nov.", "title": "Sortie endurance forêt de Sénart",
     "source": "Garmin", "type": "Gravel", "km": 68.4, "dplus": 420,
     "duration_s": 9720, "np": 218, "avgP": 195, "hr": 142, "tss": 145,
     "ifac": 0.81, "speed": 25.3},
    {"id": "d2", "date": "30 oct.", "title": "Intervalles côte de Chevreuse",
     "source": "Garmin", "type": "Route", "km": 52.1, "dplus": 680,
     "duration_s": 7200, "np": 242, "avgP": 224, "hr": 156, "tss": 168,
     "ifac": 0.90, "speed": 26.1},
    {"id": "d3", "date": "28 oct.", "title": "Zwift — Tempo Watopia",
     "source": "Zwift", "type": "Indoor", "km": 40.0, "dplus": 320,
     "duration_s": 5400, "np": 232, "avgP": 220, "hr": 148, "tss": 120,
     "ifac": 0.87, "speed": 26.7},
    {"id": "d4", "date": "25 oct.", "title": "Gravel Fontainebleau — Milly loop",
     "source": "Garmin", "type": "Gravel", "km": 82.3, "dplus": 540,
     "duration_s": 12600, "np": 205, "avgP": 188, "hr": 138, "tss": 175,
     "ifac": 0.76, "speed": 23.5},
    {"id": "d5", "date": "22 oct.", "title": "Sortie bikepacking Morvan J1",
     "source": "Garmin", "type": "Bikepacking", "km": 112.0, "dplus": 1450,
     "duration_s": 21600, "np": 178, "avgP": 162, "hr": 132, "tss": 220,
     "ifac": 0.66, "speed": 18.7},
]

DEMO_FTP_HISTORY = [
    {"date": "2024-01", "ftp": 235},
    {"date": "2024-04", "ftp": 242},
    {"date": "2024-07", "ftp": 250},
    {"date": "2024-10", "ftp": 255},
    {"date": "2025-01", "ftp": 260},
    {"date": "2025-06", "ftp": 265},
    {"date": "2025-10", "ftp": 268},
]

DEMO_LOAD = {
    "ctl": 72,
    "atl": 65,
    "tsb": 7,
    "trend": "stable",
}

DEMO_POWER_CURVE = {
    5: 820, 10: 680, 30: 480, 60: 380,
    300: 310, 600: 285, 1200: 270, 3600: 250,
}

DEMO_ZONES = [
    {"zone": "Z1 Récupération", "pct": 8, "time_min": 12},
    {"zone": "Z2 Endurance", "pct": 42, "time_min": 63},
    {"zone": "Z3 Tempo", "pct": 22, "time_min": 33},
    {"zone": "Z4 Seuil", "pct": 15, "time_min": 22},
    {"zone": "Z5 VO2max", "pct": 8, "time_min": 12},
    {"zone": "Z6 Anaérobie", "pct": 4, "time_min": 6},
    {"zone": "Z7 Neuromusculaire", "pct": 1, "time_min": 2},
]

DEMO_GOALS = [
    {"name": "FTP 280W", "current": 268, "target": 280, "unit": "W",
     "deadline": "Mars 2027", "pct": 0.72},
    {"name": "Z2 avg 260W", "current": 238, "target": 260, "unit": "W",
     "deadline": "Juin 2027", "pct": 0.45},
    {"name": "Gravel Ventoux 2027", "current": None, "target": None, "unit": "",
     "deadline": "Mai 2027", "pct": 0.30},
]

DEMO_WEEK = [
    {"day": "Lun", "type": "Repos", "done": True},
    {"day": "Mar", "type": "Z2 endurance 1h30", "done": True},
    {"day": "Mer", "type": "Intervalles 4×8min Z4", "done": False},
    {"day": "Jeu", "type": "Récupération 45min", "done": False},
    {"day": "Ven", "type": "Repos", "done": False},
    {"day": "Sam", "type": "Sortie longue 3h Z2-Z3", "done": False},
    {"day": "Dim", "type": "Récupération active 1h", "done": False},
]

DEMO_COACH_SUMMARY = (
    "Forme actuelle excellente (TSB +7). Bonne régularité cette semaine "
    "avec 3 sorties. Ta puissance Z2 progresse — continue les sorties longues "
    "en endurance pour consolider. Pense à intégrer 1 séance d'intervalles "
    "par semaine pour stimuler ta VO2max."
)
