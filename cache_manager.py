import os
import json
import time
import redis
import datetime
import csv
import threading

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

PAYLOAD_PESADO = "X" * 50000 

csv_lock = threading.Lock()

def log_metrics(result_type, latency_ms):
    with csv_lock:
        file_exists = os.path.isfile("metrics_log.csv")
        with open("metrics_log.csv", mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['timestamp', 'result_type', 'latency_ms'])
            
            
            ahora = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            writer.writerow([ahora, result_type, latency_ms])

def get_or_compute(cache_key, query_type, compute_fn, *args, **kwargs):
    start_time = time.time()
    
    cached_value = redis_client.get(cache_key)
    
    if cached_value:
        latency = (time.time() - start_time) * 1000
        log_metrics("HIT", latency)
        
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
            redis_client.set(cache_key, datos_a_guardar)
        except redis.exceptions.RedisError:
            pass
        
        latency = (time.time() - start_time) * 1000
        log_metrics("MISS", latency)
        
        return resultado_real
