import time
import random
import numpy as np
import os 

from loader import load_data

# Importamos el gestor de caché (que ya tiene el registro de métricas)
from cache_manager import get_or_compute, redis_client

# Importamos las funciones de cálculo de tu test_queries
from test_queries import q1_count, q2_area, q3_density, q4_compare, q5_confidence_dist

# Configuraciones para la simulación
ZONAS = ["Z1", "Z2", "Z3", "Z4", "Z5"]
QUERIES = ["q1", "q2", "q3", "q4", "q5"]
CONFIANZAS = [0.4, 0.6, 0.8]

def generar_pedido(tipo_distribucion="uniforme", alpha=1.2):
    """Crea una consulta basada en la distribución elegida"""
    if tipo_distribucion == "uniforme":
        q = random.choice(QUERIES)
        z1 = random.choice(ZONAS)
    else:  # Zipf: q1 y Z1 serán mucho más frecuentes
        q_idx = min(np.random.zipf(alpha) - 1, len(QUERIES) - 1)
        z1_idx = min(np.random.zipf(alpha) - 1, len(ZONAS) - 1)
        q = QUERIES[q_idx]
        z1 = ZONAS[z1_idx]
    
    conf = random.choice(CONFIANZAS)
    return q, z1, conf

def ejecutar_simulacion(nombre, tipo_dist, n_consultas, real_data):
    print(f"\n🚀 EJECUTANDO: {nombre} ({n_consultas} consultas)")
    
    # Limpiamos Redis para que la comparación sea justa (empezar en frío)
    redis_client.flushall()
    
    for i in range(n_consultas):
        q, z1, conf = generar_pedido(tipo_dist)
        
        # Ejecución según el tipo de query
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
        
        if (i+1) % 50 == 0:
            print(f"✅ Procesadas {i+1} consultas...")

if __name__ == "__main__":
    # 1. Cargar datos
    print("--- CARGANDO DATOS PARA SIMULACIÓN ---")
    datos = load_data("data/buildings.csv")
    
    # Cantidad de consultas para el experimento
    TOTAL = 200 

    # 2. Ejecutar Tráfico Uniforme
    ejecutar_simulacion("MODELO UNIFORME", "uniforme", TOTAL, datos)
    
    print("\nEsperando 2 segundos para la siguiente prueba...")
    time.sleep(2)
    
    # 3. Ejecutar Tráfico Zipf
    ejecutar_simulacion("MODELO ZIPF", "zipf", TOTAL, datos)
    
    print("\n✨ Simulación finalizada. Los datos están en 'metrics_log.csv'")