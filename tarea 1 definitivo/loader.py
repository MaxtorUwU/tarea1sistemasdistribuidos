import os, math, time
import pandas as pd

ZONES = {
    "Z1": {"name": "Providencia",     "lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600},
    "Z2": {"name": "Las Condes",      "lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550},
    "Z3": {"name": "Maipu",           "lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740},
    "Z4": {"name": "Santiago Centro", "lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630},
    "Z5": {"name": "Pudahuel",        "lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760},
}

def _bbox_area_km2(z: dict) -> float:
    lat_diff = abs(z["lat_max"] - z["lat_min"])
    lon_diff = abs(z["lon_max"] - z["lon_min"])
    lat_mid  = (z["lat_max"] + z["lat_min"]) / 2
    return lat_diff * 111.32 * lon_diff * (111.32 * math.cos(math.radians(lat_mid)))

ZONE_AREA_KM2 = {zid: _bbox_area_km2(z) for zid, z in ZONES.items()}


# ── Carga principal ──────────────────────────────────────────────────────────
def load_data(csv_path: str) -> dict:
    """
    Lee el CSV de Google Open Buildings y devuelve:
        data[zone_id] = [ {"area": float, "confidence": float}, ... ]

    Estructura optimizada para las consultas Q1–Q5 (solo los campos necesarios).
    Si el CSV no existe, genera datos sintéticos para desarrollo.
    """
    if not os.path.exists(csv_path):
        print(f"[loader] ADVERTENCIA: '{csv_path}' no encontrado → usando datos sintéticos.")
        return _generate_synthetic_data()

    t0 = time.time()
    print(f"[loader] Cargando dataset desde {csv_path} ...")

    df = pd.read_csv(
        csv_path,
        usecols=["latitude", "longitude", "area_in_meters", "confidence"],
        dtype={"latitude": "float32", "longitude": "float32",
               "area_in_meters": "float32", "confidence": "float32"},
    )
    print(f"[loader] CSV leído: {len(df):,} filas  ({(time.time()-t0):.1f}s)")

    data = {}
    for zone_id, z in ZONES.items():
        mask = (
            (df["latitude"]  >= z["lat_min"]) & (df["latitude"]  <= z["lat_max"]) &
            (df["longitude"] >= z["lon_min"]) & (df["longitude"] <= z["lon_max"])
        )
        sub = df[mask][["area_in_meters", "confidence"]].copy()
        sub.rename(columns={"area_in_meters": "area"}, inplace=True)

        data[zone_id] = sub.to_dict("records")

        mem_kb = sub.memory_usage(deep=True).sum() / 1024
        print(f"[loader]   {zone_id} ({z['name']:<18}): {len(data[zone_id]):>8,} edificios  ({mem_kb:.0f} KB)")

    total_records = sum(len(v) for v in data.values())
    print(f"[loader] Precarga completa: {total_records:,} registros en {(time.time()-t0):.2f}s")
    return data


def _generate_synthetic_data() -> dict:
    import random
    random.seed(42)
    counts = {"Z1": 25_000, "Z2": 30_000, "Z3": 40_000, "Z4": 20_000, "Z5": 15_000}
    data = {}
    for zone_id, n in counts.items():
        data[zone_id] = [
            {"area": random.uniform(30, 500), "confidence": random.uniform(0.65, 1.0)}
            for _ in range(n)
        ]
        print(f"[loader]   {zone_id}: {n:,} edificios sintéticos")
    return data
