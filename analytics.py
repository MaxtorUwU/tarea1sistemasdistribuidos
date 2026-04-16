import pandas as pd
import numpy as np

def calcular_estadisticas(file_path="metrics_log.csv"):
    if not pd.io.common.file_exists(file_path):
        print("❌ El archivo de métricas no existe. Ejecuta primero el generador.")
        return

    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Separar por tipo de resultado
    hits = df[df['result_type'] == 'HIT']
    misses = df[df['result_type'] == 'MISS']
    
    # 1. Latencias
    p50 = df['latency_ms'].median()
    p95 = df['latency_ms'].quantile(0.95)
    
    # 2. Throughput (consultas por segundo)
    # Calculado sobre el tiempo total de ejecución
    delta_tiempo = (df['timestamp'].max() - df['timestamp'].min()).total_seconds()
    throughput = len(df) / delta_tiempo if delta_tiempo > 0 else 0
    
    # 3. Cache Efficiency (Fórmula de la tarea)
    # (hits * t_cache - misses * t_db) / total
    t_cache = hits['latency_ms'].mean() if not hits.empty else 0
    t_db = misses['latency_ms'].mean() if not misses.empty else 0
    total_reqs = len(df)
    
    efficiency = (len(hits) * t_cache - len(misses) * t_db) / total_reqs

    print("\n" + "="*40)
    print("📊 REPORTE DE RENDIMIENTO END-TO-END")
    print("="*40)
    print(f"Total de peticiones : {total_reqs}")
    print(f"Tasa de Hits        : {(len(hits)/total_reqs)*100:.2f}%")
    print(f"Throughput          : {throughput:.2f} req/s")
    print(f"Latencia P50        : {p50:.2f} ms")
    print(f"Latencia P95        : {p95:.2f} ms")
    print(f"Cache Efficiency    : {efficiency:.4f}")
    print("="*40)

if __name__ == "__main__":
    calcular_estadisticas()