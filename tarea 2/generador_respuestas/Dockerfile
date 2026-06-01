FROM python:3.11-slim
WORKDIR /app
RUN pip install numpy pandas
COPY generador_respuestas.py .
CMD ["python", "-u", "generador_respuestas.py"]