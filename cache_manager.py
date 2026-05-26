import os
import json
import time
import redis
import datetime
import csv
import threading
import uuid
from kafka import KafkaProducer

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

KAFKA_HOST = os.environ.get('KAFKA_HOST', 'kafka_broker:9092')
try:
    kafka_producer = KafkaProducer(
        bootstrap_servers=[KAFKA_HOST],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        linger_ms=5
    )
except Exception:
    kafka_producer = None

PAYLOAD_PESADO = "X" * 50000 

csv_lock = threading.Lock()

def log_metrics(result_type, latency_ms, query_type="UNKNOWN", cache_key="UNKNOWN", query_id=None, retry_count=0):
    ahora = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
    q_id = query_id or str(uuid.uuid4())
    
    if kafka_producer:
        try:
            evento = {
                "query_id": q_id,
                "retry_count": retry_count,
                "timestamp": ahora,
                "result_type": result_type,
                "latency_ms": latency_ms,
                "query_type": query_type,
                "cache_key": cache_key
            }
            kafka_producer.send('metricas_cache', evento)
        except Exception:
            pass

    with csv_lock:
        file_exists = os.path.isfile("metrics_log.csv")
        with open("metrics_log.csv", mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['timestamp', 'result_type', 'latency_ms', 'query_type', 'cache_key', 'query_id', 'retry_count'])
            writer.writerow([ahora, result_type, latency_ms, query_type, cache_key, q_id, retry_count])

def get_or_compute(cache_key, query_type, compute_fn, *args, **kwargs):
    ttl = kwargs.pop('ttl', 3600)
    query_id = kwargs.pop('query_id', None)
    retry_count = kwargs.pop('retry_count', 0)
    
    start_time = time.time()
    
    cached_value = redis_client.get(cache_key)
    
    if cached_value:
        latency = (time.time() - start_time) * 1000
        log_metrics("HIT", latency, query_type, cache_key, query_id, retry_count)
        
        dato_real_str = cached_value.decode('utf-8').split("|||")[0]
        try:
            return json.loads(dato_real_str)
        except json.JSONDecodeError:
            return dato_real_str
    
    else:
        resultado_real = compute_fn(*args, **kwargs)
        
        try:
            resultado_str = json.dumps(resultado_real)
        except TypeError:
            resultado_str = str(resultado_real)
            
        datos_a_guardar = resultado_str + "|||" + PAYLOAD_PESADO
        
        try:
            redis_client.set(cache_key, datos_a_guardar, ex=ttl)
        except redis.exceptions.RedisError:
            pass
        
        latency = (time.time() - start_time) * 1000
        log_metrics("MISS", latency, query_type, cache_key, query_id, retry_count)
        
        return resultado_real
        latency = (time.time() - start_time) * 1000
        log_metrics("MISS", latency)
        
        return resultado_real
