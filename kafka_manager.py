import os
import json
import datetime
import uuid
from kafka import KafkaProducer, KafkaConsumer
from cache_manager import redis_client

KAFKA_HOST = os.environ.get('KAFKA_HOST', 'kafka_broker:9092')
TOPIC_PRINCIPAL = 'consultas_principal'
TOPIC_RETRY = 'consultas_retry'
TOPIC_DLQ = 'consultas_dlq'
GROUP_ID = os.environ.get('KAFKA_GROUP_ID', 'grupo_consultas')
MAX_RETRIES = 3

class KafkaManager:
    def __init__(self, broker=KAFKA_HOST):
        self.broker = broker
        self.producer = None

    def get_producer(self):
        if self.producer is None:
            self.producer = KafkaProducer(
                bootstrap_servers=[self.broker],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                linger_ms=10
            )
        return self.producer

    def send_event(self, topic, query_type, cache_key, detalles=None, query_id=None, retry_count=0):
        try:
            prod = self.get_producer()
            payload = {
                "query_id": query_id or str(uuid.uuid4()),
                "retry_count": retry_count,
                "created_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "query_type": query_type,
                "cache_key": cache_key,
                "detalles": detalles or {}
            }
            prod.send(topic, payload)
            prod.flush()
            return True
        except Exception:
            return False

    def listen_and_process(self):
        consumer = KafkaConsumer(
            TOPIC_PRINCIPAL,
            TOPIC_RETRY,
            bootstrap_servers=[self.broker],
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
            detalles = data.get("detalles")
            
            try:
                cached_value = redis_client.get(cache_key)
                if not cached_value:
                    raise ValueError()
            except Exception:
                if retry_count < MAX_RETRIES:
                    self.send_event(
                        topic=TOPIC_RETRY,
                        query_type=query_type,
                        cache_key=cache_key,
                        detalles=detalles,
                        query_id=query_id,
                        retry_count=retry_count + 1
                    )
                else:
                    self.send_event(
                        topic=TOPIC_DLQ,
                        query_type=query_type,
                        cache_key=cache_key,
                        detalles=detalles,
                        query_id=query_id,
                        retry_count=retry_count
                    )

kafka_client = KafkaManager()