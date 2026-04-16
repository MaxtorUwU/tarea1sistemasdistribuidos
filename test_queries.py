import numpy as np
from numpy import mean
from loader import ZONE_AREA_KM2, load_data

# Importamos nuestro nuevo gestor de caché
from cache_manager import get_or_compute

# ── Q1 — Conteo de edificios en una zona ────────────────────────────────────
def q1_count(data: dict, zone_id: str, confidence_min: float = 0.0) -> int:
    records = data[zone_id]
    return sum(1 for r in records if r["confidence"] >= confidence_min)
 
# ── Q2 — Área promedio y área total de edificaciones ─────────────────────────
def q2_area(data: dict, zone_id: str, confidence_min: float = 0.0) -> dict:
    areas = [r["area"] for r in data[zone_id] if r["confidence"] >= confidence_min]
    if not areas:
        return {"avg_area": 0.0, "total_area": 0.0, "n": 0}
    return {"avg_area": float(mean(areas)), "total_area": float(sum(areas)), "n": len(areas)}
 
# ── Q3 — Densidad de edificaciones por km² ───────────────────────────────────
def q3_density(data: dict, zone_id: str, confidence_min: float = 0.0) -> float:
    count    = q1_count(data, zone_id, confidence_min)
    area_km2 = ZONE_AREA_KM2[zone_id]
    return count / area_km2
 
# ── Q4 — Comparación de densidad entre dos zonas ────────────────────────────
def q4_compare(data: dict, zone_a: str, zone_b: str, confidence_min: float = 0.0) -> dict:
    da = q3_density(data, zone_a, confidence_min)
    db = q3_density(data, zone_b, confidence_min)
    return {"zone_a": da, "zone_b": db, "winner": zone_a if da > db else zone_b}
 
# ── Q5 — Distribución de confianza en una zona ───────────────────────────────
def q5_confidence_dist(data: dict, zone_id: str, bins: int = 5) -> list:
    scores = [r["confidence"] for r in data[zone_id]]
    counts, edges = np.histogram(scores, bins=bins, range=(0, 1))
    return [
        {"bucket": i, "min": float(edges[i]), "max": float(edges[i + 1]), "count": int(counts[i])}
        for i in range(bins)
    ]

if __name__ == "__main__":
    print("--- INICIANDO CARGA DE DATOS REALES ---")
    real_data = load_data("data/buildings.csv")

    print("\n--- INICIANDO PRUEBAS DE CACHÉ (Z1 a Z5) ---")
    
    # Parámetros globales de prueba
    zonas = ["Z1", "Z2", "Z3", "Z4", "Z5"]
    confianza = 0.6
    bins_q5 = 5

    # Bucle para probar Q1, Q2, Q3 y Q5 en CADA zona
    for zona in zonas:
        print(f"\n{'='*50}")
        print(f"=== EVALUANDO ZONA: {zona} ===")
        print(f"{'='*50}")

        # PRUEBA Q1 (Fíjate cómo ahora dice "q1" y ya no tiene el ttl=)
        key_q1 = f"count:{zona}:conf={confianza}"
        print(f"\n[Q1] Conteo - LLave: {key_q1}")
        get_or_compute(key_q1, "q1", q1_count, real_data, zona, confidence_min=confianza)
        get_or_compute(key_q1, "q1", q1_count, real_data, zona, confidence_min=confianza)

        # PRUEBA Q2
        key_q2 = f"area:{zona}:conf={confianza}"
        print(f"\n[Q2] Área - LLave: {key_q2}")
        get_or_compute(key_q2, "q2", q2_area, real_data, zona, confidence_min=confianza)
        get_or_compute(key_q2, "q2", q2_area, real_data, zona, confidence_min=confianza)

        # PRUEBA Q3
        key_q3 = f"density:{zona}:conf={confianza}"
        print(f"\n[Q3] Densidad - LLave: {key_q3}")
        get_or_compute(key_q3, "q3", q3_density, real_data, zona, confidence_min=confianza)
        get_or_compute(key_q3, "q3", q3_density, real_data, zona, confidence_min=confianza)

        # PRUEBA Q5
        key_q5 = f"confidence_dist:{zona}:bins={bins_q5}"
        print(f"\n[Q5] Distribución - LLave: {key_q5}")
        get_or_compute(key_q5, "q5", q5_confidence_dist, real_data, zona, bins=bins_q5)
        get_or_compute(key_q5, "q5", q5_confidence_dist, real_data, zona, bins=bins_q5)

    
    # Pruebas para Q4 (Comparación de zonas)
    print(f"\n{'='*50}")
    print("=== EVALUANDO Q4 (COMPARACIONES DE ZONAS) ===")
    print(f"{'='*50}")

    pares_a_comparar = [("Z1", "Z2"), ("Z3", "Z4"), ("Z5", "Z1")]

    for zona_a, zona_b in pares_a_comparar:
        key_q4 = f"compare:density:{zona_a}:{zona_b}:conf={confianza}"
        print(f"\n[Q4] Comparando {zona_a} vs {zona_b} - LLave: {key_q4}")
        get_or_compute(key_q4, "q4", q4_compare, real_data, zona_a, zona_b, confidence_min=confianza)
        get_or_compute(key_q4, "q4", q4_compare, real_data, zona_a, zona_b, confidence_min=confianza)

    print("\n--- FIN DE LAS PRUEBAS DE CACHÉ ---")