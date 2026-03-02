FROM python:3.10

WORKDIR /app

# The full python:3.10 image usually has build-essential
# If onnxruntime still has issues, we'll try something else

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables for model path and behavior
ENV PYTHONUNBUFFERED=1
ENV WAKEWORD_MODEL=hey_jarvis
ENV WAKEWORD_THRESHOLD=0.5

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
