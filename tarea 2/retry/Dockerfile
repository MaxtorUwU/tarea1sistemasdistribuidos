FROM python:3.11-slim
WORKDIR /app

# Solo necesita confluent-kafka y redis
# No necesita pandas ni numpy porque no procesa datos directamente
RUN pip install confluent-kafka redis

COPY topico_reintento.py .
CMD ["python", "-u", "topico_reintento.py"]


