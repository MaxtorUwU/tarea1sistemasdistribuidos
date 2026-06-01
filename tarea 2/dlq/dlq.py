import os
import time
import json
import csv
from datetime import datetime
from collections import defaultdict
from confluent_kafka import Consumer, KafkaException, TopicPartition

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
MAX_EMPTY_POLLS = 5

OUTPUT_FILE = os.getenv("OUTPUT_FILE", "dlq_report.csv")

def wait_for_kafka():
    print("[dlq] Esperando a Kafka...")
    while True:
        try:
            from confluent_kafka import Producer
            p = Producer({"bootstrap.servers": KAFKA_BROKER})
            p.flush(timeout=3)
            print("[dlq] Kafka listo.")
            return
        except Exception as e:
            print(f"[dlq] Kafka no disponible aún: {e}")
            time.sleep(2)

def read_dlq_messages():
    unique_group = f"dlq-analyzer-{int(time.time())}"

    consumer = Consumer({
        "bootstrap.servers":  KAFKA_BROKER,
        "group.id":           unique_group,
        "auto.offset.reset":  "earliest",
        "enable.auto.commit": False,
    })

    consumer.subscribe(["queries-dlq"])

    messages   = []   
    empty_polls = 0   #
    total_read  = 0   

    print("[dlq] Leyendo mensajes de 'queries-dlq'...")
    print(f"[dlq] Esperaré {MAX_EMPTY_POLLS} segundos sin mensajes antes de terminar.")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                empty_polls += 1
                print(f"[dlq] Sin mensajes nuevos... ({empty_polls}/{MAX_EMPTY_POLLS})")

                if empty_polls >= MAX_EMPTY_POLLS:
                    print(f"[dlq] No hay más mensajes. Total leídos: {total_read}")
                    break

                continue  

            if msg.error():
                raise KafkaException(msg.error())

            empty_polls = 0

            raw_value = msg.value()

            if raw_value is not None:
                try:
                    query = json.loads(raw_value.decode("utf-8"))
                    messages.append(query)   
                    total_read += 1         
                    if total_read % 10 == 0:
                        print(f"[dlq] Leídos: {total_read} mensajes...")
                except json.JSONDecodeError as e:
                    print(f"[dlq] Mensaje no decodificable: {e}, saltando...")
            else:
                print("[dlq] Mensaje con payload vacío, saltando...")

                
    except KeyboardInterrupt:
        print("[dlq] Interrumpido por el usuario.")
    finally:
        
        consumer.close()

    return messages



def analyze_messages(messages):
    if not messages:
        return {
            "total": 0,
            "por_query_type": {},
            "por_zona": {},
            "por_retry_count": {},
            "primera_falla": None,
            "ultima_falla": None,
            "tasa_por_minuto": 0,
        }

    por_query_type  = defaultdict(int)  
    por_zona        = defaultdict(int) 
    por_retry_count = defaultdict(int)  

    timestamps = []

    for msg in messages:

        query_type = msg.get("query_type", "desconocido")
        por_query_type[query_type] += 1

     
        zona = msg.get("zone", "desconocida")
        por_zona[zona] += 1

       
        retry_count = msg.get("retry_count", "desconocido")
        por_retry_count[str(retry_count)] += 1

        ts = msg.get("timestamp")
        if ts:
            timestamps.append(ts)

    primera_falla = None
    ultima_falla  = None
    tasa_por_minuto = 0

    if timestamps:
        primera_falla = datetime.fromtimestamp(min(timestamps)).strftime("%Y-%m-%d %H:%M:%S")
        ultima_falla  = datetime.fromtimestamp(max(timestamps)).strftime("%Y-%m-%d %H:%M:%S")

        duracion_segundos = max(timestamps) - min(timestamps)
        if duracion_segundos > 0:
            duracion_minutos = duracion_segundos / 60
            tasa_por_minuto  = round(len(messages) / duracion_minutos, 2)
        else:
            tasa_por_minuto = len(messages)

    return {
        "total":            len(messages),
        "por_query_type":   dict(por_query_type),   
        "por_zona":         dict(por_zona),
        "por_retry_count":  dict(por_retry_count),
        "primera_falla":    primera_falla,
        "ultima_falla":     ultima_falla,
        "tasa_por_minuto":  tasa_por_minuto,
    }


def save_csv(messages, output_file):
    if not messages:
        print("[dlq] No hay mensajes para guardar en CSV.")
        return

    fieldnames = [
        "id",           
        "query_type", 
        "zone",        
        "zone_b",       
        "confidence",   
        "cache_key",    
        "retry_count",  
        "timestamp",    
        "timestamp_legible",  
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")

        writer.writeheader()

        for msg in messages:
            ts = msg.get("timestamp")
            if ts:
                msg["timestamp_legible"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            else:
                msg["timestamp_legible"] = "desconocido"

            writer.writerow(msg)

    print(f"[dlq] CSV guardado en: {output_file} ({len(messages)} filas)")

def print_report(stats, messages):
    
    sep = "=" * 50

    print(f"\n{sep}")
    print("   REPORTE DE DEAD LETTER QUEUE")
    print(f"{sep}")

    if stats["total"] == 0:
        print("  La DLQ está vacía. No hay consultas irrecuperables.")
        print(sep)
        return

    print(f"  Total de consultas irrecuperables : {stats['total']}")
    print(f"  Primera falla registrada          : {stats['primera_falla']}")
    print(f"  Última falla registrada           : {stats['ultima_falla']}")
    print(f"  Tasa de fallos                    : {stats['tasa_por_minuto']} mensajes/minuto")
    print(f"\n  Distribución por tipo de query:")
    print(f"  {'-' * 35}")

    for query_type, count in sorted(
        stats["por_query_type"].items(),
        key=lambda x: x[1],
        reverse=True
    ):
        pct = round(count / stats["total"] * 100, 1)

        barra = "#" * int(pct / 2)

        print(f"  {query_type:<6} {count:>5} ({pct:>5.1f}%)  {barra}")

    print(f"\n  Distribución por zona geográfica:")
    print(f"  {'-' * 35}")

    for zona, count in sorted(
        stats["por_zona"].items(),
        key=lambda x: x[1],
        reverse=True
    ):
        pct   = round(count / stats["total"] * 100, 1)
        barra = "#" * int(pct / 2)
        print(f"  {zona:<6} {count:>5} ({pct:>5.1f}%)  {barra}")

    print(f"\n  Distribución por número de reintentos:")
    print(f"  {'-' * 35}")

    for retry_count, count in sorted(stats["por_retry_count"].items()):
        pct = round(count / stats["total"] * 100, 1)
        print(f"  retry={retry_count:<3} {count:>5} ({pct:>5.1f}%)")

    print(f"\n  Muestra de los primeros 5 mensajes:")
    print(f"  {'-' * 35}")

    for i, msg in enumerate(messages[:5], 1):
        ts = msg.get("timestamp")
        ts_legible = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "?"
        print(f"  [{i}] id={msg.get('id','?')[:8]}... "
              f"type={msg.get('query_type','?')} "
              f"zone={msg.get('zone','?')} "
              f"conf={msg.get('confidence','?')} "
              f"retries={msg.get('retry_count','?')} "
              f"hora={ts_legible}")

    print(f"\n{sep}")
    print(f"  Reporte guardado en: {OUTPUT_FILE}")
    print(sep)


def main():
    wait_for_kafka()
    time.sleep(2) 
    messages = read_dlq_messages()
    if not messages:
        print("[dlq] La DLQ está vacía. No hay consultas irrecuperables.")
        return
    print(f"[dlq] Se leyeron {len(messages)} mensajes de la DLQ.")
    stats = analyze_messages(messages)
    save_csv(messages, OUTPUT_FILE)
    print_report(stats, messages)

if __name__ == "__main__":
    main()