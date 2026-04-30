import pandas as pd
import numpy as np

def calcular_metricas_avanzadas(df_segmento):
    """Calcula el set completo de métricas para un experimento específico"""
    if df_segmento.empty:
        return {}

    # Usar .copy() para evitar el SettingWithCopyWarning de Pandas
    df_segmento = df_segmento.copy()
    df_segmento['timestamp'] = pd.to_datetime(df_segmento['timestamp'], format='mixed')
    
    hits = df_segmento[df_segmento['result_type'] == 'HIT']
    misses = df_segmento[df_segmento['result_type'] == 'MISS']
    total = len(df_segmento)
    
    # 1. Hit Rate
    hit_rate = len(hits) / total if total > 0 else 0
    
    # 2. Throughput
    duracion = (df_segmento['timestamp'].max() - df_segmento['timestamp'].min()).total_seconds()
    throughput = total / duracion if duracion > 0 else 0
    
    # 3. p50
    p50 = df_segmento['latency_ms'].median()
    
    # 4. Cache Efficiency (con validación para no dividir vacío)
    t_cache = hits['latency_ms'].mean() if len(hits) > 0 else 0.0
    t_db = misses['latency_ms'].mean() if len(misses) > 0 else 0.0
    
    efficiency = (len(hits) * t_cache - len(misses) * t_db) / total if total > 0 else 0
    
    return {
        "hit_rate": hit_rate,
        "throughput": throughput,
        "p50": p50,
        "efficiency": efficiency
    }