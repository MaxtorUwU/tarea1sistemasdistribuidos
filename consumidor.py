import os
import json
from kafka import KafkaConsumer
from kafka_manager import kafka_client
from cache_manager import get_or_compute

KAFKA_HOST = os.environ.get('KAFKA_HOST', 'kafka_broker:9092')
TOPIC_PRINCIPAL = 'consultas_principal'
TOPIC_RETRY = 'consultas_retry'
TOPIC_DLQ = 'consultas_dlq'
GROUP_ID = os.environ.get('KAFKA_GROUP_ID', 'grupo_consultas')
MAX_RETRIES = 3

def generador_respuestas(query_type, detalles):
    if detalles.get("simular_falla", False):
        raise RuntimeError()
    return {"status": "processed", "query_type": query_type, "detalles": detalles}

def iniciar_consumidor():
    consumer = KafkaConsumer(
        TOPIC_PRINCIPAL,
        TOPIC_RETRY,
        bootstrap_servers=[KAFKA_HOST],
        group_id=GROUP_ID,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    for message in consumer:
        data = message.value
        query_id = data.get("query_id")
        retry_count = data.get("retry_count", 0)
        query_type = data.get("query_type")
        cache_key = data.get("cache_key")
        detalles = data.get("detalles", {})

        try:
            get_or_compute(
                cache_key,
                query_type,
                generador_respuestas,
                query_type,
                detalles,
                query_id=query_id,
                retry_count=retry_count
            )
        except Exception:
            if retry_count < MAX_RETRIES:
                kafka_client.send_event(
                    topic=TOPIC_RETRY,
                    query_type=query_type,
                    cache_key=cache_key,
                    detalles=detalles,
                    query_id=query_id,
                    retry_count=retry_count + 1
                )
            else:
                kafka_client.send_event(
                    topic=TOPIC_DLQ,
                    query_type=query_type,
                    cache_key=cache_key,
                    detalles=detalles,
                    query_id=query_id,
                    retry_count=retry_count
                )

if __name__ == "__main__":
    iniciar_consumidor()