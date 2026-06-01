import os
import time
import json
import random
import math
import pandas as pd

from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.getenv("PORT", "8001"))
FAILURE_RATE = float(os.getenv("FAILURE_RATE", "0.0"))

# Mismas zonas que loader.py
ZONAS = {
    "Z1": {"nombre": "Providencia",     "lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600},
    "Z2": {"nombre": "Las Condes",      "lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550},
    "Z3": {"nombre": "Maipu",           "lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740},
    "Z4": {"nombre": "Santiago Centro", "lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630},
    "Z5": {"nombre": "Pudahuel",        "lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760},
}

def _bbox_area_km2(z):
    lat_diff = abs(z["lat_max"] - z["lat_min"])
    lon_diff = abs(z["lon_max"] - z["lon_min"])
    lat_mid  = (z["lat_max"] + z["lat_min"]) / 2
    return lat_diff * 111.32 * lon_diff * (111.32 * math.cos(math.radians(lat_mid)))

ZONA_AREA_KM2 = {zid: _bbox_area_km2(z) for zid, z in ZONAS.items()}

# Carga de datos
def load_data():
    csv_path = "data/buildings.csv"
    if os.path.exists(csv_path):
        print(f"[rg] Cargando dataset desde {csv_path}.")
        df = pd.read_csv(
            csv_path,
            usecols=["latitude", "longitude", "area_in_meters", "confidence"],
            dtype={"latitude": "float32", "longitude": "float32",
                   "area_in_meters": "float32", "confidence": "float32"}
        )
        data = {}
        for zid, z in ZONAS.items():
            mask = (
                (df["latitude"]  >= z["lat_min"]) & (df["latitude"]  <= z["lat_max"]) &
                (df["longitude"] >= z["lon_min"]) & (df["longitude"] <= z["lon_max"])
            )
            sub = df[mask][["area_in_meters", "confidence"]].copy()
            sub.rename(columns={"area_in_meters": "area"}, inplace=True)
            data[zid] = sub.to_dict("records")
            print(f"[rg]   {zid}: {len(data[zid]):,} edificios")
        return data
    else:
        # Sin CSV real, genera datos sintéticos para que el sistema funcione
        print("[rg] buildings.csv no encontrado, usando datos sintéticos")
        import random as rnd
        rnd.seed(42)
        counts = {"Z1": 25000, "Z2": 30000, "Z3": 40000, "Z4": 20000, "Z5": 15000}
        return {
            zid: [{"area": rnd.uniform(30, 500), "confidence": rnd.uniform(0.65, 1.0)}
                  for _ in range(n)]
            for zid, n in counts.items()
        }

# Cargar datos al arrancar el servidor (una sola vez)
DATA = load_data()

#  Mismas funciones Q1-Q5 de test_queries.py
def q1_count(zone_id, confidence_min=0.0):
    return sum(1 for r in DATA[zone_id] if r["confidence"] >= confidence_min)

def q2_area(zone_id, confidence_min=0.0):
    areas = [r["area"] for r in DATA[zone_id] if r["confidence"] >= confidence_min]
    if not areas:
        return {"avg_area": 0.0, "total_area": 0.0, "n": 0}
    return {
        "avg_area":   float(sum(areas) / len(areas)),
        "total_area": float(sum(areas)),
        "n":          len(areas)
    }

def q3_density(zone_id, confidence_min=0.0):
    count = q1_count(zone_id, confidence_min)
    return count / ZONA_AREA_KM2[zone_id]

def q4_compare(zone_a, zone_b, confidence_min=0.0):
    da = q3_density(zone_a, confidence_min)
    db = q3_density(zone_b, confidence_min)
    return {"zone_a": da, "zone_b": db, "winner": zone_a if da > db else zone_b}

def q5_confidence_dist(zone_id, bins=5):
    import numpy as np
    scores = [r["confidence"] for r in DATA[zone_id]]
    counts, edges = np.histogram(scores, bins=bins, range=(0, 1))
    return [
        {"bucket": i, "min": float(edges[i]), "max": float(edges[i+1]), "count": int(counts[i])}
        for i in range(bins)
    ]

# ── Handler HTTP ─────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # silenciar los logs por defecto del servidor HTTP

    def do_GET(self):
        # Endpoint de salud para verificar que el servicio está vivo
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

    def do_POST(self):
        # Leer el cuerpo del request
        length = int(self.headers.get("Content-Length", 0))
        consulta  = json.loads(self.rfile.read(length))

        # Simular fallo aleatorio si FAILURE_RATE > 0
        # Para los escenarios de prueba
        if random.random() < FAILURE_RATE:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Service unavailable"}).encode())
            return

        # Extrae parámetros del mensaje
        q      = consulta.get("query_type", "q1")
        zone   = consulta.get("zone", "Z1")
        zone_b = consulta.get("zone_b", "Z2")
        conf   = float(consulta.get("confidence", 0.6))

        # Ejecutar la función correspondiente
        try:
            if   q == "q1": result = q1_count(zone, conf)
            elif q == "q2": result = q2_area(zone, conf)
            elif q == "q3": result = q3_density(zone, conf)
            elif q == "q4": result = q4_compare(zone, zone_b, conf)
            elif q == "q5": result = q5_confidence_dist(zone)
            else:           result = None
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # Responder con el resultado
        respuesta = {
            "query_id":    consulta.get("id"),
            "query_type":  q,
            "zone":        zone,
            "result":      result,
            "processed_at": time.time(),
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(respuesta).encode())

if __name__ == "__main__":
    print(f"[rg] Response Generator corriendo en puerto {PORT} | failure_rate={FAILURE_RATE}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()