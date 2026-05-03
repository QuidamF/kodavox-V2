FROM python:3.10-slim

# Instalar dependencias del sistema operativo, portaudio para el micrófono y git
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    build-essential \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements primero para aprovechar caché
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Comando por defecto
CMD ["python", "main.py"]
