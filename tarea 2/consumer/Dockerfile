FROM python:3.11-slim
WORKDIR /app
RUN pip install confluent-kafka redis
COPY consumidor_kafka.py .
CMD ["python", "-u", "consumidor_kafka.py"]