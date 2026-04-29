FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if required by torch/audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

# Pre-download Silero VAD model if possible (optional, but speeds up startup)
RUN python -c "from silero_vad import VoiceActivityDetector; VoiceActivityDetector()" || true

COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
