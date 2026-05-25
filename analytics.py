import pandas as pd
import numpy as np

def calcular_metricas_avanzadas(df_segmento):
    if df_segmento.empty:
        return {}

    df_segmento = df_segmento.copy()
    df_segmento['timestamp'] = pd.to_datetime(df_segmento['timestamp'], format='mixed')
    
    hits = df_segmento[df_segmento['result_type'] == 'HIT']
    misses = df_segmento[df_segmento['result_type'] == 'MISS']
    total = len(df_segmento)
    
    hit_rate = len(hits) / total if total > 0 else 0
    
    
    duracion = (df_segmento['timestamp'].max() - df_segmento['timestamp'].min()).total_seconds()
    throughput = total / duracion if duracion > 0 else 0
    
    p50 = df_segmento['latency_ms'].median()
    
    t_cache = hits['latency_ms'].mean() if len(hits) > 0 else 0.0
    t_db = misses['latency_ms'].mean() if len(misses) > 0 else 0.0
    
    efficiency = (len(hits) * t_cache - len(misses) * t_db) / total if total > 0 else 0
    
    return {
        "hit_rate": hit_rate,
        "throughput": throughput,
        "p50": p50,
        "efficiency": efficiency
    }
