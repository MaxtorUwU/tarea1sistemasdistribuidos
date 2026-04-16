import os
import time
import pandas as pd
import matplotlib.pyplot as plt
from cache_manager import redis_client
from generador_trafico import ejecutar_simulacion, load_data

def set_redis_config(size_mb, policy):
    """Cambia la configuración de Redis al vuelo"""
    try:
        redis_client.config_set("maxmemory", f"{size_mb}mb")
        redis_client.config_set("maxmemory-policy", policy)
        print(f"⚙️ Configurado: {size_mb}MB - Política: {policy}")
    except Exception as e:
        print(f"❌ Error configurando Redis: {e}")

def correr_fase_4():
    datos = load_data("data/buildings.csv")
    resultados = []

    # --- EXPERIMENTO 1: TAMAÑOS DE CACHÉ ---
    # Probamos con 50MB, 200MB, 500MB (usaremos 5, 10, 20 para notar evicción con tu dataset pequeño si es necesario)
    print("\n--- TEST: TAMAÑOS DE CACHÉ ---")
    for size in [50, 200, 500]:
        set_redis_config(size, "allkeys-lfu")
        # Ejecutamos tráfico para llenar y medir
        ejecutar_simulacion(f"Size_{size}", "zipf", 300, datos)
        
        # Leemos el CSV generado para extraer el hit rate
        df = pd.read_csv("metrics_log.csv")
        last_300 = df.tail(300)
        hit_rate = (last_300['result_type'] == 'HIT').sum() / 300
        resultados.append({"experiment": "Size", "value": size, "hit_rate": hit_rate})

    # --- EXPERIMENTO 2: POLÍTICAS ---
    print("\n--- TEST: POLÍTICAS DE EVICCIÓN ---")
    for policy in ["allkeys-lru", "allkeys-lfu", "allkeys-random"]:
        set_redis_config(50, policy) # Tamaño fijo para comparar peras con peras
        ejecutar_simulacion(f"Policy_{policy}", "zipf", 300, datos)
        
        df = pd.read_csv("metrics_log.csv")
        last_300 = df.tail(300)
        hit_rate = (last_300['result_type'] == 'HIT').sum() / 300
        resultados.append({"experiment": "Policy", "value": policy, "hit_rate": hit_rate})

    # Guardar resultados finales para graficar
    res_df = pd.DataFrame(resultados)
    res_df.to_csv("resultados_fase4.csv", index=False)
    print("\n✅ Experimentos terminados. Datos guardados en 'resultados_fase4.csv'")

if __name__ == "__main__":
    correr_fase_4()