#!/usr/bin/env python3
"""
Verifica el CSV descargado y muestra estadísticas por zona.
Uso: python verify_buildings.py
"""

import os, sys, math
import pandas as pd

ZONES = {
    "Z1": {"name": "Providencia",     "lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600},
    "Z2": {"name": "Las Condes",      "lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550},
    "Z3": {"name": "Maipu",           "lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740},
    "Z4": {"name": "Santiago Centro", "lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630},
    "Z5": {"name": "Pudahuel",        "lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760},
}

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "buildings.csv")

if not os.path.exists(CSV_PATH):
    print(f"[ERROR] No se encontró {CSV_PATH}")
    print("  Ejecuta primero: python download_buildings.py")
    sys.exit(1)

df = pd.read_csv(CSV_PATH)
print(f"CSV cargado: {len(df):,} filas  |  columnas: {list(df.columns)}")
print(f"Archivo: {os.path.getsize(CSV_PATH)/1024/1024:.1f} MB\n")

def bbox_area_km2(z):
    lat_diff = abs(z["lat_max"] - z["lat_min"])
    lon_diff = abs(z["lon_max"] - z["lon_min"])
    lat_mid  = (z["lat_max"] + z["lat_min"]) / 2
    return lat_diff * 111.32 * lon_diff * 111.32 * math.cos(math.radians(lat_mid))

print(f"{'Zona':<6} {'Nombre':<18} {'Edificios':>10} {'Área km²':>9} {'Densidad/km²':>13} {'Confianza avg':>14}")
print("-" * 75)
for zid, z in ZONES.items():
    mask = (
        (df["latitude"]  >= z["lat_min"]) & (df["latitude"]  <= z["lat_max"]) &
        (df["longitude"] >= z["lon_min"]) & (df["longitude"] <= z["lon_max"])
    )
    sub = df[mask]
    n = len(sub)
    area = bbox_area_km2(z)
    density = n / area if area > 0 else 0
    conf_avg = sub["confidence"].mean() if n > 0 else 0
    print(f"{zid:<6} {z['name']:<18} {n:>10,} {area:>9.2f} {density:>13.1f} {conf_avg:>14.3f}")

print()
print("Distribución de confianza (dataset completo):")
bins = [0, 0.5, 0.65, 0.7, 0.8, 0.9, 1.01]
labels = ["<0.5", "0.5-0.65", "0.65-0.7", "0.7-0.8", "0.8-0.9", "≥0.9"]
for label, (lo, hi) in zip(labels, zip(bins, bins[1:])):
    n = ((df["confidence"] >= lo) & (df["confidence"] < hi)).sum()
    bar = "█" * int(n / len(df) * 40)
    print(f"  {label:<10} {n:>8,}  {bar}")
