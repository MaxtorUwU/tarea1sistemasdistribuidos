#!/usr/bin/env python3
"""
Filtra el archivo 967_buildings.csv.gz (u otros tiles) y genera
data/buildings.csv con solo las 5 zonas predefinidas de Santiago.

Uso:
    # Desde la carpeta tarea1/
    python3 -m venv venv
    source venv/bin/activate
    pip install pandas tqdm

    # Con el gz en la misma carpeta:
    python filter_buildings.py --input 967_buildings.csv.gz

    # Si tienes varios tiles:
    python filter_buildings.py --input 967_buildings.csv.gz 94c_buildings.csv.gz
"""

import gzip, os, sys, argparse
import pandas as pd

# ── Zonas predefinidas (del enunciado) ──────────────────────────────────────
ZONES = {
    "Z1": {"name": "Providencia",     "lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600},
    "Z2": {"name": "Las Condes",      "lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550},
    "Z3": {"name": "Maipu",           "lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740},
    "Z4": {"name": "Santiago Centro", "lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630},
    "Z5": {"name": "Pudahuel",        "lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760},
}

# Bounding box global que engloba todas las zonas (con margen)
GLOBAL_LAT_MIN = min(z["lat_min"] for z in ZONES.values()) - 0.02
GLOBAL_LAT_MAX = max(z["lat_max"] for z in ZONES.values()) + 0.02
GLOBAL_LON_MIN = min(z["lon_min"] for z in ZONES.values()) - 0.02
GLOBAL_LON_MAX = max(z["lon_max"] for z in ZONES.values()) + 0.02

COLS = ["latitude", "longitude", "area_in_meters", "confidence"]


def read_gz(path: str) -> pd.DataFrame:
    print(f"\n→ Leyendo {os.path.basename(path)} ...")
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  Tamaño: {size_mb:.1f} MB")

    # Leer en chunks para no saturar RAM con archivos grandes
    chunks = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for chunk in pd.read_csv(f, usecols=COLS, chunksize=500_000):
            mask = (
                (chunk["latitude"]  >= GLOBAL_LAT_MIN) & (chunk["latitude"]  <= GLOBAL_LAT_MAX) &
                (chunk["longitude"] >= GLOBAL_LON_MIN) & (chunk["longitude"] <= GLOBAL_LON_MAX)
            )
            filtered = chunk[mask]
            if len(filtered) > 0:
                chunks.append(filtered)
            total_read = sum(len(c) for c in chunks)
            print(f"  ... procesando chunks | encontrados hasta ahora: {total_read:,}", end="\r")

    if not chunks:
        print(f"\n  [aviso] Ningún registro de {os.path.basename(path)} cae en las zonas de Santiago.")
        return pd.DataFrame(columns=COLS)

    df = pd.concat(chunks, ignore_index=True)
    print(f"\n  {len(df):,} registros dentro del área de Santiago")
    return df


def show_stats(df: pd.DataFrame):
    import math

    def bbox_area_km2(z):
        lat_diff = abs(z["lat_max"] - z["lat_min"])
        lon_diff = abs(z["lon_max"] - z["lon_min"])
        lat_mid  = (z["lat_max"] + z["lat_min"]) / 2
        return lat_diff * 111.32 * lon_diff * 111.32 * math.cos(math.radians(lat_mid))

    print(f"\n{'Zona':<6} {'Nombre':<18} {'Edificios':>10} {'Área km²':>9} {'Dens./km²':>10} {'Conf. avg':>10}")
    print("─" * 68)
    for zid, z in ZONES.items():
        mask = (
            (df["latitude"]  >= z["lat_min"]) & (df["latitude"]  <= z["lat_max"]) &
            (df["longitude"] >= z["lon_min"]) & (df["longitude"] <= z["lon_max"])
        )
        sub = df[mask]
        n = len(sub)
        area = bbox_area_km2(z)
        density = n / area if area > 0 else 0
        conf = sub["confidence"].mean() if n > 0 else 0
        print(f"{zid:<6} {z['name']:<18} {n:>10,} {area:>9.2f} {density:>10.1f} {conf:>10.3f}")

    print(f"\n  Total en todas las zonas: {len(df):,} edificios")

    # Distribución de confianza
    print("\nDistribución de confianza:")
    bins = [(0, 0.5), (0.5, 0.65), (0.65, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    labels = ["< 0.50", "0.50–0.65", "0.65–0.70", "0.70–0.80", "0.80–0.90", "≥ 0.90"]
    for label, (lo, hi) in zip(labels, bins):
        n = int(((df["confidence"] >= lo) & (df["confidence"] < hi)).sum())
        pct = n / len(df) * 100 if len(df) > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"  {label:<12} {n:>8,}  {pct:5.1f}%  {bar}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", nargs="+", required=True,
                        help="Archivos .csv.gz a procesar (uno o varios)")
    parser.add_argument("--output", default="data/buildings.csv",
                        help="Ruta de salida (default: data/buildings.csv)")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    frames = []
    for path in args.input:
        if not os.path.exists(path):
            print(f"[ERROR] No se encontró: {path}")
            sys.exit(1)
        df = read_gz(path)
        if len(df) > 0:
            frames.append(df)

    if not frames:
        print("\n[ERROR] Ningún tile contiene datos para las zonas de Santiago.")
        print("Verifica que el tile sea correcto. Para Santiago se esperan tiles como:")
        print("  967_buildings.csv.gz, 94c_buildings.csv.gz, 94d_buildings.csv.gz")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["latitude", "longitude"]
    )

    # Mostrar estadísticas
    show_stats(combined)

    # Guardar
    combined.to_csv(args.output, index=False)
    size_mb = os.path.getsize(args.output) / 1024 / 1024
    print(f"\n✓ CSV guardado en: {args.output}  ({size_mb:.1f} MB, {len(combined):,} filas)")
    print("\nPróximo paso:")
    print("  docker compose up --build")


if __name__ == "__main__":
    main()
