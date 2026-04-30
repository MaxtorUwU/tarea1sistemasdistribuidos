FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Asegúrate de que este nombre sea IGUAL al de tu archivo en la carpeta
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cambia 'run.py' por el script que inicia todo si tiene otro nombre
CMD ["python", "run.py"]