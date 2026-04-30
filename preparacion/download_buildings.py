#!/usr/bin/env python3
"""
Descarga y filtra el dataset Google Open Buildings
para las 5 zonas predefinidas de Santiago.

Uso:
    pip install requests pandas tqdm
    python download_buildings.py
"""

import os, sys, gzip, requests, pandas as pd
from tqdm import tqdm

# ── Zonas predefinidas (del enunciado) ─────────────────────────────────────
ZONES = {
    "Z1": {"name": "Providencia",     "lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600},
    "Z2": {"name": "Las Condes",      "lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550},
    "Z3": {"name": "Maipu",           "lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740},
    "Z4": {"name": "Santiago Centro", "lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630},
    "Z5": {"name": "Pudahuel",        "lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760},
}

# Bounding box global que cubre todas las zonas (para filtrar rápido)
LAT_MIN = min(z["lat_min"] for z in ZONES.values()) - 0.01
LAT_MAX = max(z["lat_max"] for z in ZONES.values()) + 0.01
LON_MIN = min(z["lon_min"] for z in ZONES.values()) - 0.01
LON_MAX = max(z["lon_max"] for z in ZONES.values()) + 0.01

# ── Tiles S2 que cubren Santiago (Región Metropolitana) ────────────────────
# Identificados manualmente desde el mapa del dataset.
# Santiago cae principalmente en las celdas S2 nivel 4: 94d, 94c, 947, 946
TILE_URLS = [
    "https://storage.googleapis.com/open-buildings-data/v3/points_s2_level_4_gzip/94d_buildings.csv.gz",
    "https://storage.googleapis.com/open-buildings-data/v3/points_s2_level_4_gzip/94c_buildings.csv.gz",
    "https://storage.googleapis.com/open-buildings-data/v3/points_s2_level_4_gzip/947_buildings.csv.gz",
    "https://storage.googleapis.com/open-buildings-data/v3/points_s2_level_4_gzip/946_buildings.csv.gz",
]

OUT_DIR  = os.path.join(os.path.dirname(__file__), "data")
OUT_CSV  = os.path.join(OUT_DIR, "buildings.csv")
COLS     = ["latitude", "longitude", "area_in_meters", "confidence"]

os.makedirs(OUT_DIR, exist_ok=True)


def download_tile(url: str, dest: str):
    """Descarga un tile con barra de progreso."""
    r = requests.get(url, stream=True, timeout=60)
    if r.status_code == 404:
        print(f"  [skip] {url} → 404, tile no encontrado")
        return False
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True,
                                      desc=os.path.basename(dest)) as bar:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))
    return True


def filter_zone(df: pd.DataFrame, zone: dict) -> pd.DataFrame:
    return df[
        (df["latitude"]  >= zone["lat_min"]) & (df["latitude"]  <= zone["lat_max"]) &
        (df["longitude"] >= zone["lon_min"]) & (df["longitude"] <= zone["lon_max"])
    ]


def main():
    frames = []
    tmp_dir = os.path.join(OUT_DIR, "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    for url in TILE_URLS:
        fname = os.path.basename(url)
        gz_path = os.path.join(tmp_dir, fname)

        # Descarga (reutiliza si ya existe)
        if os.path.exists(gz_path):
            print(f"  [cache] {fname} ya descargado")
        else:
            print(f"\n→ Descargando {fname}")
            ok = download_tile(url, gz_path)
            if not ok:
                continue

        # Leer y filtrar por bounding box global
        print(f"  Leyendo y filtrando {fname}...")
        try:
            with gzip.open(gz_path, "rt") as f:
                df = pd.read_csv(f, usecols=COLS)
        except Exception as e:
            print(f"  [error] No se pudo leer {fname}: {e}")
            continue

        mask = (
            (df["latitude"]  >= LAT_MIN) & (df["latitude"]  <= LAT_MAX) &
            (df["longitude"] >= LON_MIN) & (df["longitude"] <= LON_MAX)
        )
        chunk = df[mask]
        print(f"  {len(chunk):,} registros dentro del área de Santiago")
        if len(chunk) > 0:
            frames.append(chunk)

    if not frames:
        print("\n[ERROR] No se encontraron datos. Revisa la conexión o los tile IDs.")
        sys.exit(1)

    # Combinar todos los tiles
    combined = pd.concat(frames, ignore_index=True).drop_duplicates()
    print(f"\n→ Total combinado: {len(combined):,} edificios en Región Metropolitana")

    # Mostrar conteo por zona
    print("\nEdificios por zona predefinida:")
    for zid, zone in ZONES.items():
        n = len(filter_zone(combined, zone))
        print(f"  {zid} ({zone['name']}): {n:,} edificios")

    # Guardar CSV final
    combined.to_csv(OUT_CSV, index=False)
    size_mb = os.path.getsize(OUT_CSV) / 1024 / 1024
    print(f"\n✓ Guardado en: {OUT_CSV}  ({size_mb:.1f} MB)")
    print("  Puedes levantar el sistema con: docker compose up --build")


if __name__ == "__main__":
    main()
