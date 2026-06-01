import os
import time
import uuid
import json
import random
import numpy as np
from confluent_kafka import Producer

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
QUERIES_POR_SEGUNDO = float(os.getenv("QUERIES_POR_SEGUNDO", "10"))
DISTRIBUCION = os.getenv("DISTRIBUCION", "zipf")
ZIPF_ALPHA = float(os.getenv("ZIPF_ALPHA", "1.2"))
DURACION_SEGUNDOS = int(os.getenv("DURACION_SEGUNDOS", "120"))


ZONAS = ["Z1", "Z2", "Z3", "Z4", "Z5"]
QUERIES = ["q1", "q2", "q3", "q4", "q5"]
CONFIANZAS = [0.4, 0.6, 0.8]


def zipf_distribucion(items):
    """ Toma una lista y devuelve un elemento siguiendo la distribucion zipf """
    n = len(items)
    pesos = np.array([1.0 / (i ** ZIPF_ALPHA) for i in range(1, n + 1)])
    pesos /= pesos.sum()

    return np.random.choice(items, p = pesos)


def build_cache_key(q, z1, conf, z2 = None):
    if q == "q1": return f"count:{z1}:conf={conf}"
    if q == "q2": return f"area:{z1}:conf={conf}"
    if q == "q3": return f"density:{z1}:conf={conf}"
    if q == "q4": return f"compare:{z1}:{z2}:conf={conf}"
    if q == "q5": return f"dist:{z1}:bins=5"


def wait_for_kafka():
    """ Se intenta crear un Producer si kafka esta listo. En caso contrario, espera 3 segundos """
    print("[trafico] Esperando a Kafka...")
    while True:
        try:
            p = Producer({"bootstrap.servers": KAFKA_BROKER})
            p.flush(timeout=3)
            print("[trafico] Kafka listo.")
            return
        except Exception as e:
            print(f"[trafico] Kafka aun no disponible: {e}")
            time.sleep(3)

def delivery_report(err, msg):
    """ Si err es None, no hay error. En caso contrario, se imprime """
    if err:
        print(f"[trafico] Error enviando mensaje: {err}")


def main():
    wait_for_kafka()
    time.sleep(5)  
    
    producer = Producer({
        "bootstrap.servers": KAFKA_BROKER,
        "acks": "all",
    })

    print(f"[trafico] Iniciando — {QUERIES_POR_SEGUNDO} QPS | dist={DISTRIBUCION} | duración={DURACION_SEGUNDOS}s")

    start_time = time.time()
    enviadas = 0

    while True:
        t_transcurrido = time.time() - start_time
        if t_transcurrido >= DURACION_SEGUNDOS:
            break

        q  = zipf_distribucion(QUERIES) if DISTRIBUCION == "zipf" else random.choice(QUERIES)
        z1 = zipf_distribucion(ZONAS)   if DISTRIBUCION == "zipf" else random.choice(ZONAS)
        conf = random.choice(CONFIANZAS)
        z2 = random.choice([z for z in ZONAS if z != z1]) if q == "q4" else None

        mensaje = {
            "id": str(uuid.uuid4()),
            "query_type": q,
            "zone": z1,
            "zone_b": z2,
            "confidence": conf,
            "cache_key": build_cache_key(q, z1, conf, z2),  
            "timestamp": time.time(),
            "retry_count": 0,
        }
        
        producer.produce(
            "queries",
            value=json.dumps(mensaje).encode("utf-8"),
            callback=delivery_report
        )
        producer.poll(0)
        enviadas += 1

        if enviadas % 50 == 0:
            print(f"[traffic] [{t_transcurrido:.1f}s] Enviadas {enviadas} | última: {q} zona={z1} conf={conf}")

        time.sleep(1.0 / QUERIES_POR_SEGUNDO)


    producer.flush()
    print(f"[trafico] Finalizado. Total enviado: {enviadas} consultas")


if __name__ == "__main__":
    main()
