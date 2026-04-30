#!/bin/bash

# Asegúrate de dar permisos de ejecución: chmod +x run_test.sh

echo "=========================================="
echo "1. Optimizando Imagen de Docker"
echo "=========================================="
docker build --progress=plain -t python-tester .

echo "=========================================="
echo "2. Iniciando Infraestructura de Redis"
echo "=========================================="
docker-compose down
docker-compose up -d

echo "Esperando 5 segundos a que Redis inicie..."
sleep 5

echo "=========================================="
echo "3. Ejecutando Simulaciones"
echo "=========================================="
# Ejecutamos Python UNA SOLA VEZ. 
# run.py ya contiene los bucles para probar LRU, LFU y los MegaBytes.

docker run --rm \
    --network container:redis_lfu_500MB \
    -v "$(pwd)":/app \
    -e REDIS_HOST=localhost \
    -e REDIS_PORT=6379 \
    python-tester

echo "=========================================="
echo "4. Finalizando Proceso"
echo "=========================================="
docker-compose down

echo "🚀 ¡Proceso completado! Revisa los archivos .png generados en tu carpeta."