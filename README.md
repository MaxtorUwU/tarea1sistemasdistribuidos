# Simulación de Políticas de Caché en Redis (Tarea 1)

Este proyecto simula y evalúa el comportamiento de un servidor de caché Redis sometido a alta concurrencia. El objetivo principal es analizar cómo diferentes tamaños de memoria, políticas de evicción (LRU vs LFU) y distribuciones de tráfico (Uniforme y Zipf) impactan en el rendimiento del sistema (Hit Rate, Latencia, Throughput y Tasa de Evicción).

---

## Estructura del Proyecto y Función de cada Archivo

El sistema está diseñado con una arquitectura modular para separar la infraestructura, la lógica de negocio y el análisis de datos.

### 1. Infraestructura (Docker)
* **`docker-compose.yml`**: Define y levanta el contenedor del servidor Redis que actuará como caché.
* **`Dockerfile`**: Construye el entorno de ejecución aislando las dependencias de Python.
* **`requirements.txt`**: Lista las librerías necesarias para ejecutar el proyecto (`redis`, `pandas`, `numpy`, `matplotlib`, `seaborn`).
* **`run_test.sh`**: Es el orquestador principal. Un script de Bash que automatiza todo el ciclo de vida: construye la imagen de Docker, levanta Redis, ejecuta la simulación en Python y apaga la infraestructura al finalizar.

### 2. Core y Lógica de Datos
* **`loader.py`**: Encargado de cargar el dataset principal (`buildings.csv`) en memoria al inicio de la ejecución para que las consultas tengan datos reales sobre los cuales operar.
* **`test_queries.py`**: Contiene la lógica matemática y de filtrado de las 5 consultas del sistema (e.g., conteo, área, densidad, etc.).
* **`cache_manager.py`**: Es el componente crítico que actúa como middleware. Intercepta las consultas, verifica si existen en Redis (HIT) o si debe calcularlas y guardarlas (MISS). Implementa protecciones `try-except` para evitar caídas por errores de Out of Memory (OOM) en Redis bajo concurrencia extrema, y registra los tiempos de latencia bloqueando el acceso al CSV (`threading.Lock()`) para evitar corrupción de datos por hilos concurrentes.
* **`data/buildings.csv`**: Carpeta y archivo que contienen el dataset original (requerido para la ejecución).

### 3. Simulación y Control
* **`generador_trafico.py`**: Genera miles de consultas sintéticas basándose en dos modelos probabilísticos: Distribución Uniforme o Distribución Zipf. Lanza las consultas de forma concurrente utilizando un `ThreadPoolExecutor` para estresar la caché.
* **`run.py`**: El cerebro de la simulación. Se conecta a Redis y dinámicamente reconfigura sus parámetros al vuelo (`maxmemory` a 50MB, 200MB o 500MB y `maxmemory-policy` a `allkeys-lru` o `allkeys-lfu`). Coordina la ejecución de todos los escenarios de forma secuencial.

### 4. Analítica y Resultados
* **`analytics.py`**: Una vez que la simulación termina, este script procesa el archivo de registro `metrics_log.csv` usando Pandas. Calcula métricas avanzadas (Hit Rate, P50, Eviction Rate, Throughput) y utiliza Seaborn para generar los gráficos comparativos finales.

---

## Requisitos Previos

Para ejecutar este proyecto, necesitas tener instalado en tu máquina:
* Docker
* Docker Compose

*Nota: No necesitas instalar Python localmente para la simulación, ya que todo se ejecuta de forma aislada dentro de los contenedores de Docker.*

---

## Guía de Ejecución Paso a Paso

Sigue estos pasos para reproducir el experimento completo:

Paso 1: Preparación del Dataset
Asegúrate de que el archivo del dataset se encuentre en la ruta correcta (`data/buildings.csv`). 

Para esto, extrae el archivo `.zip` proporcionado. Dentro encontrarás la carpeta `data`, la cual debes mover al directorio principal del proyecto. La estructura del proyecto debe verse exactamente de la siguiente manera:

```text
TAREA1/
├── data/
│   ├── .gitkeep
│   └── buildings.csv
├── preparacion/
│   ├── download_buildings.py
│   ├── filtrado.py
│   └── verify_buildings.py
├── analytics.py
├── cache_manager.py
├── docker-compose.yml
├── Dockerfile
├── generador_trafico.py
├── loader.py
├── reporte.py
├── requirements.txt
├── run_test.sh
├── run.py
└── test_queries.py



Paso 2: Otorgar permisos de ejecución
Abre tu terminal en la raíz del proyecto y dale permisos de ejecución al script orquestador:
```bash
chmod +x run_test.sh

Paso 3: Ejecutar el sh que hace absolutamente todo por ti

y de ahi es 
./run_test.sh


