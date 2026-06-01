FROM python:3.11-slim
WORKDIR /app
RUN pip install confluent-kafka numpy
COPY  generador_trafico.py .
CMD ["python", "-u", "generador_trafico.py"]
