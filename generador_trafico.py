import time
import random
import numpy as np
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from kafka_manager import kafka_client

ZONAS = ["Z1", "Z2", "Z3", "Z4", "Z5"]
QUERIES = ["q1", "q2", "q3", "q4", "q5"]
TOPIC_PRINCIPAL = 'consultas_principal'

def generar_pedido(tipo_distribucion="uniforme", alpha=1.2):
    if tipo_distribucion == "uniforme":
        q = random.choice(QUERIES)
        z1 = random.choice(ZONAS)
    else:
        q_idx = min(np.random.zipf(alpha) - 1, len(QUERIES) - 1)
        z1_idx = min(np.random.zipf(alpha) - 1, len(ZONAS) - 1)
        q = QUERIES[q_idx]
        z1 = ZONAS[z1_idx]
    
    conf = round(random.uniform(0.4, 0.9), 3)
    return q, z1, conf

def enviar_consulta_kafka(tipo_dist):
    q, z1, conf = generar_pedido(tipo_dist)
    
    cache_key = ""
    detalles = {"confidence_min": conf, "z1": z1}
    
    if q == "q1":
        cache_key = f"count:{z1}:conf={conf}"
    elif q == "q2":
        cache_key = f"area:{z1}:conf={conf}"
    elif q == "q3":
        cache_key = f"density:{z1}:conf={conf}"
    elif q == "q4":
        z2 = random.choice([z for z in ZONAS if z != z1])
        cache_key = f"compare:{z1}:{z2}:conf={conf}"
        detalles["z2"] = z2
    elif q == "q5":
        cache_key = f"dist:{z1}:bins=5"
        detalles["bins"] = 5

    query_id = str(uuid.uuid4())
    kafka_client.send_event(
        topic=TOPIC_PRINCIPAL,
        query_type=q,
        cache_key=cache_key,
        detalles=detalles,
        query_id=query_id,
        retry_count=0
    )

def ejecutar_simulacion(nombre_experimento, tipo_dist, num_consultas, real_data=None):
    print(f"Iniciando: {nombre_experimento}")
    with ThreadPoolExecutor(max_workers=20) as executor:
        list(executor.map(lambda _: enviar_consulta_kafka(tipo_dist), range(num_consultas)))

def ejecutar_spike(tipo_dist, duracion_segundos, tasa_por_segundo, real_data=None):
    print(f"Iniciando spike: {duracion_segundos}s a {tasa_por_segundo} req/s")
    inicio = time.time()
    with ThreadPoolExecutor(max_workers=50) as executor:
        while time.time() - inicio < duracion_segundos:
            segundo_inicio = time.time()
            for _ in range(tasa_por_segundo):
                executor.submit(enviar_consulta_kafka, tipo_dist)
            diff = time.time() - segundo_inicio
            if diff < 1.0:
                time.sleep(1.0 - diff)
if __name__ == "__main__":
    print("--- PRUEBA INDIVIDUAL DEL GENERADOR ---")
    datos = load_data("data/buildings.csv")
    ejecutar_simulacion("test_local", "uniform", 1000, datos)
