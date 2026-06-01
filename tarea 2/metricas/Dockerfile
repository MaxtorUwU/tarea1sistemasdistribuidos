FROM python:3.11-slim
WORKDIR /app

# threading y http.server vienen incluidos en Python (librería estándar)
# solo necesitamos confluent-kafka y redis
RUN pip install confluent-kafka redis

COPY metricas.py .

CMD ["python", "-u", "metricas.py"]