FROM python:3.11-slim
WORKDIR /app

# Solo necesita confluent-kafka
# csv, json, datetime, collections vienen en la librería estándar
RUN pip install confluent-kafka

COPY dlq.py .

# No usamos CMD porque este servicio no corre indefinidamente
# Se ejecuta manualmente cuando se quiere analizar la DLQ
CMD ["python", "-u", "dlq.py"]