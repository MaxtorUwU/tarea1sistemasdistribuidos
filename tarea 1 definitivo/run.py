import os
import time
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Crucial para entornos Docker/Servidor
import matplotlib.pyplot as plt

from cache_manager import redis_client
from generador_trafico import ejecutar_simulacion, load_data
from analytics import calcular_metricas_avanzadas 
from reporte import generar_reporte_completo 

def set_redis_config(size_MB, policy):
    """Cambia la configuración de Redis usando bytes exactos para evitar bugs de versión"""
    try:
        # Convertimos MB a Bytes matemáticamente (Ej: 50 * 1024 * 1024)
        bytes_exactos = size_MB * 1024 * 1024
        redis_client.config_set("maxmemory", bytes_exactos)
        redis_client.config_set("maxmemory-policy", policy)
        
        redis_client.config_resetstat()
        print(f"⚙️ Configurado en Redis: {size_MB}MB ({bytes_exactos} bytes) | Política: {policy}")
    except Exception as e:
        print(f"❌ Error configurando Redis: {e}")

def obtener_evicciones():
    """Obtiene el número de llaves expulsadas (evicted_keys) desde el último resetstat"""
    info = redis_client.info("stats")
    return info.get('evicted_keys', 0)

def correr_experimentos():
    # ¡NUEVO! Borrar el log anterior para que no se mezcle la basura
    if os.path.exists("metrics_log.csv"):
        os.remove("metrics_log.csv")
        print("🗑️ Archivo metrics_log.csv viejo eliminado. Empezando en limpio.")

    # 1. Carga inicial del dataset (el filtrado)
    datos = load_data("data/buildings.csv")
    resultados_finales = []
    
    # 2. Definición de escenarios (6 combinaciones)
    configuraciones = [
        ('allkeys-lru', 50), ('allkeys-lru', 200), ('allkeys-lru', 500),
        ('allkeys-lfu', 50), ('allkeys-lfu', 200), ('allkeys-lfu', 500)
    ]
    
    # 3. Definición de distribuciones requeridas
    distribuciones = ["zipf", "uniform"]

    # 4. Bucle anidado: Distribuciones x Configuraciones
    for dist in distribuciones:
        for politica, tamano_MB in configuraciones:
            print(f"\n🚀 EJECUTANDO ESCENARIO: {politica} | {tamano_MB}MB | Dist: {dist.upper()}")
            
            set_redis_config(tamano_MB, politica)
            
            # Puedes usar 10000 o 50000. Dejaremos 10000 como lo tenías recién.
            num_consultas = 20000
            
            # Pasamos la distribución elegida al generador de tráfico
            ejecutar_simulacion(f"test_{politica}_{tamano_MB}MB_{dist}", dist, num_consultas, datos)
            
            # Recolección de métricas de hardware
            time.sleep(0.5)
            evicciones = obtener_evicciones()
            
            # Procesamiento de logs
            time.sleep(1) 
            if os.path.exists("metrics_log.csv"):
                df_log = pd.read_csv("metrics_log.csv")
                df_segmento = df_log.tail(num_consultas)
                
                metricas = calcular_metricas_avanzadas(df_segmento)
                tasa_eviccion = evicciones / (num_consultas / 60) 
                
                # Consolidamos resultados incluyendo la distribución
                metricas.update({
                    "policy": politica, 
                    "size_MB": tamano_MB,
                    "distribution": dist,  # ¡Clave para los gráficos!
                    "evictions": evicciones,
                    "eviction_rate": tasa_eviccion
                })
                
                resultados_finales.append(metricas)
                
                # Usamos .get por seguridad por si falla la métrica
                hit_rate = metricas.get('hit_rate', 0.0)
                print(f"📊 Resultado: Hit Rate {hit_rate:.2f} | Evicciones: {evicciones}")
            else:
                print(f"⚠️ Error: No se encontró metrics_log.csv para el escenario {politica} {tamano_MB}MB")

    # 5. Exportación y Generación de Reportes
    if resultados_finales:
        df_final = pd.DataFrame(resultados_finales)
        df_final.to_csv("resultados_detallados.csv", index=False)
        
        print("\n" + "="*50)
        print("✅ EXPERIMENTOS FINALIZADOS CON ÉXITO")
        print("📈 Generando gráficos comparativos separados...")
        print("="*50)
        
        generar_reporte_completo("resultados_detallados.csv")
    else:
        print("❌ Error crítico: No se pudieron recolectar datos de los experimentos.")

if __name__ == "__main__":
    correr_experimentos()