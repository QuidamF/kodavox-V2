# Microservicio de Speech-to-Text con Whisper

Este proyecto es un microservicio de transcripción de audio a texto basado en Python. Utiliza **FastAPI** para la API y **faster-whisper** para el motor de transcripción, una implementación optimizada del modelo Whisper de OpenAI.

El servicio funciona de manera 100% offline (después de la descarga inicial del modelo) y está diseñado para ser ejecutado en un contenedor de **Docker**, garantizando la persistencia de los modelos para evitar descargas repetidas.

## Características

- **API Rápida y Moderna**: Basada en FastAPI.
- **Alta Eficiencia**: Utiliza `faster-whisper` para una transcripción más rápida y con menor uso de memoria.
- **Dos Endpoints Principales**:
  - Transcripción por lotes a partir de un archivo de audio.
  - Transcripción en tiempo real mediante streaming con WebSockets.
- **Configurable**: Permite seleccionar el tamaño del modelo y el dispositivo de ejecución (CPU/GPU) mediante variables de entorno.
- **Persistencia de Modelos**: Los modelos se descargan una sola vez y persisten gracias al uso de volúmenes de Docker.
- **Contenerizado**: Listo para desplegar con Docker.

## Requisitos

- [Docker](https://www.docker.com/get-started) instalado en tu sistema.
- Si deseas usar GPU, necesitas [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

## Guía de Inicio Rápido (Recomendado con Docker Compose)

La forma más sencilla de levantar el servicio es usando `docker-compose`.

### 1. Configuración
Crea una copia del archivo de configuración de ejemplo y ajústalo si es necesario.

```bash
cp .env.example .env
```
**Variables de entorno:**
- `MODEL_SIZE`: Modelo a utilizar (`tiny`, `base`, `small`, `medium`, `large-v3`).
- `DEVICE`: Dispositivo de ejecución (`cpu`, `cuda`).
- `MODELS_DIR`: Directorio interno para guardar los modelos (por defecto `/app/models`).

### 2. Levantar el Servicio
Con Docker y Docker Compose instalados, ejecuta el siguiente comando:

```bash
docker-compose up -d --build
```
Este comando construirá la imagen, creará un volumen nombrado (`whisper_models`) para la persistencia de los modelos y levantará el servicio en segundo plano. La primera vez, descargará el modelo, lo que puede tardar un poco.

Para detener el servicio, ejecuta:
```bash
docker-compose down
```

### Método Alternativo (con Docker Build y Run)

Si prefieres no usar `docker-compose`, puedes seguir estos pasos:

#### 1. Construir la Imagen
```bash
docker build -t whisper-microservice .
```
#### 2. Ejecutar el Contenedor
**Para CPU:**
```bash
# Crea un directorio local para los modelos
mkdir -p my-whisper-models

# Ejecuta el contenedor enlazando el directorio
docker run -d -p 8000:8000 \
  -v "$(pwd)/my-whisper-models:/app/models" \
  -e MODEL_SIZE=${MODEL_SIZE} \
  -e DEVICE=${DEVICE} \
  --name whisper-service \
  whisper-microservice
```
**Para GPU (NVIDIA):**
```bash
docker run -d -p 8000:8000 \
  -v "$(pwd)/my-whisper-models:/app/models" \
  --gpus all \
  -e MODEL_SIZE=${MODEL_SIZE} \
  -e DEVICE=${DEVICE} \
  --name whisper-service \
  whisper-microservice
```

## Documentación de la API

Una vez que el contenedor está en ejecución, la API estará disponible en `http://localhost:8000`.

### Endpoint: `POST /api/v1/transcribe`

Este endpoint transcribe un archivo de audio completo.

**Ejemplo con `curl`:**

```bash
curl -X POST -F "audio_file=@/ruta/a/tu/archivo.wav" http://localhost:8000/api/v1/transcribe
```

**Respuesta exitosa:**

```json
{
  "transcription": "El texto transcrito de tu audio aparecerá aquí."
}
```

### Endpoint: `WS /api/v1/streaming`

Este endpoint permite la transcripción en tiempo real a través de un WebSocket.

**Flujo de trabajo:**
1. Conéctate al WebSocket.
2. Envía fragmentos de audio como mensajes de bytes.
3. Cuando hayas terminado de enviar audio, envía un mensaje de texto en formato JSON: `{"action": "stop"}`.
4. El servidor procesará el audio completo y te devolverá la transcripción en un mensaje de texto.

**Ejemplo de cliente en Python:**

Crea un archivo `ws_client.py` y pega el siguiente código. Asegúrate de tener `websockets` instalado (`pip install websockets`).

```python
import asyncio
import websockets
import json

async def stream_audio(file_path):
    uri = "ws://localhost:8000/api/v1/streaming"
    async with websockets.connect(uri) as websocket:
        print("Conectado al servidor WebSocket.")
        
        # Envía el audio en fragmentos
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(1024)  # Lee 1KB a la vez
                if not chunk:
                    break
                await websocket.send(chunk)
                await asyncio.sleep(0.05) # Pequeña pausa para simular streaming

        # Envía el mensaje de finalización
        await websocket.send(json.dumps({"action": "stop"}))
        print("Mensaje 'stop' enviado. Esperando transcripción...")

        # Espera la respuesta del servidor
        response = await websocket.recv()
        print("\nRespuesta del servidor:")
        print(json.loads(response))

if __name__ == "__main__":
    # Reemplaza 'test.wav' con la ruta a tu archivo de audio
    asyncio.run(stream_audio("test.wav"))
```

Ejecuta el cliente: `python ws_client.py`.
