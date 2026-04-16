import os
import json
import redis
import time
import csv
from datetime import datetime
from dotenv import load_dotenv

# 1. CARGAR CONFIGURACIÓN
load_dotenv()

REDIS_HOST      = os.getenv("REDIS_HOST", "localhost")
MAX_MEMORY      = os.getenv("MAX_MEMORY", "10mb")        
EVICTION_POLICY = os.getenv("EVICTION_POLICY", "allkeys-lru")

TTL_CONFIG = {
    "q1": int(os.getenv("TTL_Q1", 60)),
    "q2": int(os.getenv("TTL_Q2", 120)),
    "q3": int(os.getenv("TTL_Q3", 180)),
    "q4": int(os.getenv("TTL_Q4", 300)),
    "q5": int(os.getenv("TTL_Q5", 60))
}

METRICS_FILE = "metrics_log.csv"

# 2. CONEXIÓN A REDIS (Aseguramos que se llame redis_client)
redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

try:
    redis_client.config_set('maxmemory', MAX_MEMORY)
    redis_client.config_set('maxmemory-policy', EVICTION_POLICY)
    print(f"🔧 [REDIS CONFIG] Memoria Máx: {MAX_MEMORY} | Política de Evicción: {EVICTION_POLICY}")
except Exception as e:
    print(f"⚠️ [REDIS WARNING] No se pudo configurar la política: {e}")

# Inicializar CSV de métricas
if not os.path.exists(METRICS_FILE):
    with open(METRICS_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "query_type", "result_type", "latency_ms"])

# 3. REGISTRO DE MÉTRICAS
def registrar_metrica(query_type, result_type, latency):
    with open(METRICS_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), query_type, result_type, latency])

# 4. FUNCIÓN PRINCIPAL
def get_or_compute(cache_key: str, query_type: str, compute_func, *args, **kwargs):
    start_time = time.time()
    
    try:
        cached_data = redis_client.get(cache_key)
    except Exception:
        cached_data = None

    if cached_data:
        latency = (time.time() - start_time) * 1000
        registrar_metrica(query_type, "HIT", latency)
        print(f"  🟢 [CACHE HIT] {cache_key} ({latency:.2f}ms)")
        return json.loads(cached_data)
        
    # MISS: Calcular
    result = compute_func(*args, **kwargs)
    
    latency = (time.time() - start_time) * 1000
    registrar_metrica(query_type, "MISS", latency)
    
    ttl = TTL_CONFIG.get(query_type, 60)
    try:
        redis_client.setex(cache_key, ttl, json.dumps(result))
    except Exception:
        pass
        
    print(f"  🔴 [CACHE MISS] {cache_key} ({latency:.2f}ms)")
    return result