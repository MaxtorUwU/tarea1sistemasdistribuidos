import time
import random
import numpy as np
import os 
from concurrent.futures import ThreadPoolExecutor # <--- IMPORT PARA CONCURRENCIA

from loader import load_data
from cache_manager import get_or_compute, redis_client
from test_queries import q1_count, q2_area, q3_density, q4_compare, q5_confidence_dist

ZONAS = ["Z1", "Z2", "Z3", "Z4", "Z5"]
QUERIES = ["q1", "q2", "q3", "q4", "q5"]

def generar_pedido(tipo_distribucion="uniforme", alpha=1.2):
    """Crea una consulta basada en la distribución elegida"""
    if tipo_distribucion == "uniforme":
        q = random.choice(QUERIES)
        z1 = random.choice(ZONAS)
    else:  
        q_idx = min(np.random.zipf(alpha) - 1, len(QUERIES) - 1)
        z1_idx = min(np.random.zipf(alpha) - 1, len(ZONAS) - 1)
        q = QUERIES[q_idx]
        z1 = ZONAS[z1_idx]
    
    # Miles de combinaciones únicas obligan a la caché a llenarse
    conf = round(random.uniform(0.4, 0.9), 3) 
    
    return q, z1, conf

def ejecutar_una_consulta(tipo_dist, real_data):
    """Función 'worker' que ejecuta una sola consulta de forma aislada"""
    q, z1, conf = generar_pedido(tipo_dist)
    
    if q == "q1":
        get_or_compute(f"count:{z1}:conf={conf}", "q1", q1_count, real_data, z1, confidence_min=conf)
    elif q == "q2":
        get_or_compute(f"area:{z1}:conf={conf}", "q2", q2_area, real_data, z1, confidence_min=conf)
    elif q == "q3":
        get_or_compute(f"density:{z1}:conf={conf}", "q3", q3_density, real_data, z1, confidence_min=conf)
    elif q == "q4":
        z2 = random.choice([z for z in ZONAS if z != z1])
        get_or_compute(f"compare:{z1}:{z2}:conf={conf}", "q4", q4_compare, real_data, z1, z2, confidence_min=conf)
    elif q == "q5":
        get_or_compute(f"dist:{z1}:bins=5", "q5", q5_confidence_dist, real_data, z1, bins=5)

def ejecutar_simulacion(nombre_experimento, tipo_dist, num_consultas, real_data):
    """Ejecuta la simulación enviando cientos de consultas en paralelo"""
    print(f"\n--- INICIANDO TRÁFICO CONCURRENTE: {nombre_experimento} ---")
    
    inicio = time.time()
    
    # 🔥 AQUÍ CREAMOS LA CONCURRENCIA (max_workers = 20 hilos simultáneos)
    with ThreadPoolExecutor(max_workers=20) as executor:
        # Mapeamos la función 'worker' a la cantidad de consultas que queramos
        # Esto envía todas las tareas al pool de hilos para ejecutarse en paralelo
        list(executor.map(lambda _: ejecutar_una_consulta(tipo_dist, real_data), range(num_consultas)))
            
    fin = time.time()
    duracion = fin - inicio
    print(f"✅ {num_consultas} consultas procesadas en {duracion:.2f} segundos.")
    print(f"🚀 Tasa de llegada (Throughput simulación): {num_consultas/duracion:.2f} req/s")

if __name__ == "__main__":
    print("--- PRUEBA INDIVIDUAL DEL GENERADOR ---")
    datos = load_data("data/buildings.csv")
    ejecutar_simulacion("test_local", "uniform", 1000, datos)