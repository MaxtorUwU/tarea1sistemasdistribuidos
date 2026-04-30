import os
import json
import time
import redis
import datetime
import csv
import threading # <--- NUEVO IMPORT

# 1. Configuración de la conexión a Redis
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

# 2. Definimos el peso artificial (50 KB de relleno) a nivel global
PAYLOAD_PESADO = "X" * 50000 

# 🔥 CREAMOS UN CANDADO PARA EVITAR CORRUPCIÓN DEL CSV
csv_lock = threading.Lock()

def log_metrics(result_type, latency_ms):
    with csv_lock:
        file_exists = os.path.isfile("metrics_log.csv")
        with open("metrics_log.csv", mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['timestamp', 'result_type', 'latency_ms'])
            
            # 🔥 CAMBIO AQUÍ: Forzamos un formato con decimales siempre (.%f)
            ahora = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            writer.writerow([ahora, result_type, latency_ms])

def get_or_compute(cache_key, query_type, compute_fn, *args, **kwargs):
    start_time = time.time()
    
    # Intentar obtener el dato de la caché
    cached_value = redis_client.get(cache_key)
    
    if cached_value:
        # ¡ES UN CACHE HIT!
        latency = (time.time() - start_time) * 1000
        log_metrics("HIT", latency)
        
        # Le quitamos el payload basura que le pegamos antes
        dato_real_str = cached_value.decode('utf-8').split("|||")[0]
        try:
            return json.loads(dato_real_str)
        except json.JSONDecodeError:
            return dato_real_str
    
    else:
        # ¡ES UN CACHE MISS!
        resultado_real = compute_fn(*args, **kwargs)
        
        # Convertir a texto para poder concatenar
        try:
            resultado_str = json.dumps(resultado_real)
        except TypeError:
            resultado_str = str(resultado_real)
            
        # Concatenar el resultado real con el PAYLOAD_PESADO
        datos_a_guardar = resultado_str + "|||" + PAYLOAD_PESADO
        
        # 🔥 CAMBIO AQUÍ: Protegemos el guardado contra picos de OOM
        try:
            redis_client.set(cache_key, datos_a_guardar)
        except redis.exceptions.RedisError:
            # Si Redis rechaza el comando por estar demasiado lleno en ese milisegundo (OOM)
            # lo ignoramos amablemente. El programa seguirá vivo y devolverá el resultado.
            pass
        
        latency = (time.time() - start_time) * 1000
        log_metrics("MISS", latency)
        
        return resultado_real