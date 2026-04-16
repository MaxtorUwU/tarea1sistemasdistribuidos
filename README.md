# Tarea 1 — Sistemas Distribuidos 2026-1
## Plataforma de análisis geoespacial con caché distribuida

**Profesor:** Nicolás Hidalgo  
**Entrega:** Viernes 17 de abril de 2026 — vía Canvas  

---

## Descripción del sistema

Sistema distribuido que simula consultas geoespaciales sobre el dataset **Google Open Buildings** (Región Metropolitana de Santiago), con un sistema de caché Redis que optimiza el acceso a la información.

### Arquitectura

```
Generador de Tráfico ──► Sistema de Caché (Redis) ──► Generador de Respuestas
                                  │                          │
                                  └────────────────────────► Almacenamiento de Métricas
```

El sistema está compuesto por **4 módulos principales**:

| Módulo | Archivo | Descripción |
|---|---|---|
| Generador de Tráfico | `generador_trafico.py` | Simula consultas con distribución Zipf y Uniforme |
| Sistema de Caché | `cache_manager.py` | Intercepta consultas, gestiona Redis, registra métricas |
| Generador de Respuestas | `test_queries.py` | Implementa Q1–Q5 en memoria sobre el dataset |
| Almacenamiento de Métricas | `analytics.py` / `metrics_log.csv` | Registra y analiza hits, misses, latencias |

---

## Estructura del proyecto

```
tarea1/
├── docker-compose.yml          # Orquestación de servicios
├── .env                        # Variables de configuración (creado manualmente)
│
├── data/
│   └── buildings.csv           # Dataset filtrado de Google Open Buildings
│
├── loader.py                   # Precarga del dataset en memoria
├── cache_manager.py            # Gestor de caché Redis + registro de métricas
├── test_queries.py             # Implementación de consultas Q1–Q5
├── generador_trafico.py        # Generador de tráfico Zipf/Uniforme
├── analytics.py                # Análisis de métricas y estadísticas
├── run.py                      # Orquestador de experimentos (tamaño/política)
├── reporte.py                  # Generación de gráficos
│
├── filtrado.py                 # Script para filtrar el CSV original
├── download_buildings.py       # Script de descarga del dataset
├── verify_buildings.py         # Verificación del dataset por zona
│
└── metrics_log.csv             # Registro de eventos del sistema
```

---

## Requisitos

- Python 3.10+
- Docker y Docker Compose
- Redis (via Docker)
- Dataset `967_buildings.csv` descargado de Google Open Buildings

```bash  (en el terminal en donde esta la tarea 1)
# Crear venv e instalar todo de una vez
python3 -m venv venv
source venv/bin/activate
pip install pandas numpy matplotlib seaborn python-dotenv redis
```

---

## Paso 1 — Preparar el dataset

El dataset debe filtrarse para quedarse solo con las 5 zonas de Santiago definidas en el enunciado:

```bash
# El archivo 967_buildings.csv debe estar en el directorio actual
python filtrado.py --input 967_buildings.csv.gz
# Resultado: data/buildings.csv (~5-15 MB con ~163k edificios)
```

Para verificar que el dataset quedó correcto:

```bash
python verify_buildings.py
```

Deberías ver algo como:

```
Zona   Nombre             Edificios   Área km²   Densidad/km²   Confianza avg
Z1     Providencia           15,639       10.34        1512.2           0.812
Z2     Las Condes            27,853       15.52        1794.9           0.795
Z3     Maipu                 74,117       20.66        3586.6           0.781
Z4     Santiago Centro       24,453       12.41        1970.7           0.798
Z5     Pudahuel              21,345       20.68        1032.2           0.773
```

### Zonas predefinidas (del enunciado)

| Zona | Nombre | lat_min | lat_max | lon_min | lon_max |
|---|---|---|---|---|---|
| Z1 | Providencia | -33.445 | -33.420 | -70.640 | -70.600 |
| Z2 | Las Condes | -33.420 | -33.390 | -70.600 | -70.550 |
| Z3 | Maipú | -33.530 | -33.490 | -70.790 | -70.740 |
| Z4 | Santiago Centro | -33.460 | -33.430 | -70.670 | -70.630 |
| Z5 | Pudahuel | -33.470 | -33.430 | -70.810 | -70.760 |

---

## Paso 2 — Levantar Redis con Docker

```bash
docker compose up -d redis-cache
```

El `docker-compose.yml` levanta Redis configurable vía variables de entorno:

```yaml
services:
  redis-cache:
    image: redis:latest
    ports:
      - "6379:6379"

  python-app:
    build: .
    environment:
      - REDIS_HOST=redis-cache
      - EVICTION_POLICY=allkeys-lfu
      - MAX_MEMORY=5mb
      - TTL_Q1=10
    depends_on:
      - redis-cache
```

### Variables de configuración (.env)

Crear un archivo `.env` en la raíz del proyecto:

```env
# Conexión Redis
REDIS_HOST=localhost

# Política de evicción: allkeys-lru | allkeys-lfu | allkeys-random
EVICTION_POLICY=allkeys-lru

# Tamaño máximo de caché: 50mb | 200mb | 500mb
MAX_MEMORY=200mb

# TTL por tipo de consulta (segundos)
TTL_Q1=60
TTL_Q2=120
TTL_Q3=180
TTL_Q4=300
TTL_Q5=60
```

---

## Paso 3 — Consultas Q1–Q5 (precarga en memoria)

Las consultas operan directamente sobre el dataset cargado en memoria por `loader.py`, sin acceso a base de datos en tiempo de ejecución.

### `loader.py` — Precarga del dataset

```python
data = load_data("data/buildings.csv")
# Resultado: dict { "Z1": [{"area": float, "confidence": float}, ...], ... }
```

### Consultas implementadas en `test_queries.py`

**Q1 — Conteo de edificios**
```python
# Cache key: count:{zone_id}:conf={confidence_min}
q1_count(data, "Z1", confidence_min=0.7)  # → 12,847
```

**Q2 — Área promedio y total**
```python
# Cache key: area:{zone_id}:conf={confidence_min}
q2_area(data, "Z1", confidence_min=0.0)
# → {"avg_area": 158.4, "total_area": 2477801.0, "n": 15639}
```

**Q3 — Densidad por km²**
```python
# Cache key: density:{zone_id}:conf={confidence_min}
q3_density(data, "Z1", confidence_min=0.0)  # → 1512.2 edif/km²
```

**Q4 — Comparación entre zonas**
```python
# Cache key: compare:density:{zone_a}:{zone_b}:conf={confidence_min}
q4_compare(data, "Z1", "Z2", confidence_min=0.0)
# → {"zone_a": 1512.2, "zone_b": 1794.9, "winner": "Z2"}
```

**Q5 — Distribución de confianza**
```python
# Cache key: confidence_dist:{zone_id}:bins={bins}
q5_confidence_dist(data, "Z1", bins=5)
# → [{"bucket": 0, "min": 0.0, "max": 0.2, "count": 0}, ...]
```

---

## Paso 4 — Ejecutar el sistema completo

### Prueba básica con caché (test_queries.py)

Ejecuta todas las consultas sobre todas las zonas, registrando hits y misses en `metrics_log.csv`:

```bash
python test_queries.py
```

Cada consulta se ejecuta **dos veces** — la primera es un MISS (computa y guarda en Redis), la segunda es un HIT (responde desde caché):

```
[Q1] Conteo - Llave: count:Z1:conf=0.6
  🔴 [CACHE MISS] count:Z1:conf=0.6 (8.23ms)
  🟢 [CACHE HIT]  count:Z1:conf=0.6 (1.45ms)
```

### Simulación de tráfico (generador_trafico.py)

Simula 200 consultas con distribución uniforme y luego 200 con Zipf:

```bash
python generador_trafico.py
```

```
🚀 EJECUTANDO: MODELO UNIFORME (200 consultas)
✅ Procesadas 50 consultas...
✅ Procesadas 100 consultas...
...
🚀 EJECUTANDO: MODELO ZIPF (200 consultas)
...
✨ Simulación finalizada. Los datos están en 'metrics_log.csv'
```

---

## Paso 5 — Experimentos de análisis

El script `run.py` ejecuta todos los experimentos requeridos por el enunciado automáticamente:

```bash
python run.py
```

Corre dos baterías de experimentos:

### Experimento 1 — Impacto del tamaño de caché

Prueba con **50 MB, 200 MB y 500 MB** usando política LRU y tráfico Zipf:

| Tamaño | Hit Rate esperado |
|---|---|
| 50 MB | Bajo — más evictions |
| 200 MB | Medio |
| 500 MB | Alto — pocas evictions |

### Experimento 2 — Políticas de evicción

Fija 50 MB de caché y compara **LRU, LFU y RANDOM** (aproximación a FIFO):

| Política | Comportamiento |
|---|---|
| `allkeys-lru` | Elimina el menos recientemente usado |
| `allkeys-lfu` | Elimina el menos frecuentemente usado |
| `allkeys-random` | Elimina aleatoriamente (aproxima FIFO) |

Resultados guardados en `resultados_fase4.csv`.

---

## Paso 6 — Ver métricas y generar gráficos

### Reporte de rendimiento (analytics.py)

```bash
python analytics.py
```

```
========================================
📊 REPORTE DE RENDIMIENTO END-TO-END
========================================
Total de peticiones :  2200
Tasa de Hits        : 68.45%
Throughput          : 52.31 req/s
Latencia P50        :  3.21 ms
Latencia P95        : 11.84 ms
Cache Efficiency    : -2.4731
========================================
```

### Métricas registradas

| Métrica | Definición | Dónde se calcula |
|---|---|---|
| Hit rate | hits / (hits + misses) | `analytics.py` |
| Throughput | consultas exitosas / segundo | `analytics.py` |
| Latencia p50/p95 | percentiles de tiempo de respuesta | `analytics.py` |
| Eviction rate | evictions / minuto | Redis INFO + `cache_manager.py` |
| Cache efficiency | (hits·t_cache − misses·t_db) / total | `analytics.py` |

### Generar gráficos (reporte.py)

```bash
python reporte.py
```

Genera dos gráficos PNG a partir de `resultados_fase4.csv`:
- `grafico_tamano_cache.png` — Hit rate vs tamaño de caché
- `grafico_politicas.png` — Comparación de políticas de evicción

---

## Flujo completo de ejecución

```bash
# 1. Preparar entorno
python3 -m venv venv && source venv/bin/activate
pip install redis pandas numpy matplotlib seaborn python-dotenv

# 2. Levantar Redis
docker compose up -d redis-cache

# 3. Preparar datos
python filtrado.py --input 967buildings.csv.gz
python verify_buildings.py

# 4. Prueba rápida de consultas con caché
python test_queries.py

# 5. Simulación de tráfico completa
python generador_trafico.py

# 6. Experimentos de tamaño/política
python run.py

# 7. Ver resultados
python analytics.py
python reporte.py
```

---

## Cumplimiento de requisitos del enunciado

| Requisito | Implementación |
|---|---|
| Generador de Tráfico con Zipf y Uniforme | `generador_trafico.py` — `generar_pedido(tipo_distribucion=...)` |
| Caché con Redis, TTL y políticas LRU/LFU/FIFO | `cache_manager.py` — configura Redis al vuelo |
| Cache keys según formato del enunciado | `cache_manager.py` — `count:Z1:conf=0.6`, `density:Z1:conf=0.6`, etc. |
| Consultas Q1–Q5 en memoria | `test_queries.py` — sin acceso a BD en tiempo real |
| Precarga del dataset | `loader.py` — carga `data/buildings.csv` al iniciar |
| Almacenamiento de métricas | `metrics_log.csv` — CSV con timestamp, tipo, resultado, latencia |
| Hit rate, Throughput, Latencia p50/p95 | `analytics.py` |
| Cache efficiency formula del enunciado | `analytics.py` — `(hits·t_cache − misses·t_db) / total` |
| Análisis tamaño 50/200/500 MB | `run.py` — experimento tamaños |
| Comparación LRU vs LFU vs FIFO | `run.py` — experimento políticas |
| Gráficos comparativos | `reporte.py` — genera PNG |
| Docker | `docker-compose.yml` |

---

## Notas técnicas

- **Sin base de datos en tiempo real**: toda la información es precargada en memoria al iniciar (`loader.py`). Las consultas Q1–Q5 operan sobre esta estructura en memoria.
- **TTL por consulta**: cada tipo de consulta tiene su propio TTL configurable en `.env`. Q1 expira más rápido (60s) que Q4 (300s) porque el conteo de edificios es la consulta más frecuente.
- **Distribución Zipf**: usa `numpy.random.zipf(alpha)` con `alpha=1.2` por defecto. Con Zipf, Z1 y Q1 concentran la mayoría del tráfico, favoreciendo el cache hit rate.
- **Métricas**: se registran en `metrics_log.csv` en tiempo real durante la ejecución. El archivo persiste entre ejecuciones — usar `redis_client.flushall()` para limpiar Redis entre experimentos (ya implementado en `run.py`).

---

## Repositorio

Enlace al repositorio: **[agregar URL de GitHub/GitLab aquí]**