# Offline TTS Service with Voice Cloning

Este proyecto proporciona un servicio de Text-to-Speech (TTS) offline de alta calidad utilizando FastAPI y Docker. La principal característica es la capacidad de clonar voces a partir de una breve muestra de audio, gracias al modelo XTTS-v2 de Coqui TTS.

## Características

- **TTS Offline:** Todo el procesamiento se realiza localmente, sin necesidad de conexión a internet.
- **Clonación de Voz (Zero-shot):** Clona una voz a partir de una muestra de audio de 5 a 15 segundos.
- **API Dual:**
  - **Modo Batch:** Convierte un texto completo en un único archivo de audio.
  - **Modo Streaming:** Genera y transmite audio en tiempo real, reduciendo la latencia percibida.
- **Aceleración por GPU:** Diseñado para aprovechar las GPUs de NVIDIA a través de Docker para un rendimiento óptimo.
- **Contenerizado:** Empaquetado con Docker para una fácil implementación y portabilidad.

## Prerrequisitos

1.  **Docker:** Asegúrate de tener Docker instalado en tu sistema. [Instrucciones de instalación](https://docs.docker.com/engine/install/).
2.  **NVIDIA Container Toolkit:** Para el soporte de GPU en Docker. Es **esencial** para el buen rendimiento.
    - [Guía de instalación de NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
3.  **Drivers de NVIDIA:** Debes tener los drivers de NVIDIA más recientes para tu GPU.

## Cómo Ejecutar el Servicio (con Docker Compose)

Gracias a Docker Compose, el flujo de trabajo es mucho más sencillo y eficiente.

### Paso 1: Añadir una Voz de Muestra

1.  Graba o consigue un archivo de audio claro y sin ruido de fondo de la voz que deseas clonar. El formato puede ser **cualquiera compatible con FFmpeg (MP3, MP4, OGG, FLAC, WAV, etc.)**. El servicio lo convertirá automáticamente a WAV.
2.  La duración ideal es entre 5 y 15 segundos.
3.  Coloca este archivo en el directorio `voices` del proyecto. Para los ejemplos de la API, se asume que el archivo se llama `my_voice_sample.wav` (o `my_voice_sample.mp3`, `my_voice_sample.mp4`, etc., según el formato que uses).

    ```
    /
    |-- voices/
    |   |-- my_voice_sample.mp3  <-- TU ARCHIVO DE VOZ AQUÍ (puede ser .wav, .mp4, etc.)
    |-- app/
    |-- ...
    ```

### Paso 2: Iniciar el Servicio

Abre una terminal en la raíz del proyecto y ejecuta el siguiente comando:

```bash
docker-compose up --build
```


- **La primera vez:** Este comando construirá la imagen e iniciará el servicio. La primera vez descargará el modelo, pero gracias a la nueva configuración de volúmenes, **se guardará permanentemente** y no volverá a descargarse en futuros reinicios.
- **Siguientes veces:** Ejecuta `docker-compose up`. El arranque será mucho más rápido.

### IMPORTANTE: Formato de Audio

Para maximizar el rendimiento, el servicio ahora **solo acepta archivos `.wav`** como muestra de voz. 
- Debes convertir tus audios a `.wav` antes de subirlos a la carpeta `voices`.
- Se recomienda una frecuencia de muestreo de 24kHz para evitar cualquier remuestreo interno, aunque el sistema aceptará otros WAV válidos.

### Caché de Voces (Mejora de Rendimiento)

El sistema ahora cuenta con una memoria caché inteligente:
1. La primera vez que usas una voz (ej. `my_voice.wav`), el sistema tardará un poco más (computando el "ADN" de la voz).
2. Las siguientes peticiones con esa misma voz serán **instantáneas**, ya que reutiliza los datos calculados.

Para detener el servicio, presiona `Ctrl + C` en la terminal.

Si todo ha ido bien, verás en la terminal los logs del servidor, indicando que el modelo se ha cargado y el servicio está en línea en `http://localhost:8000`.

## Uso de la API

Puedes interactuar con el servicio utilizando cualquier cliente HTTP. Aquí tienes unos ejemplos con `curl`.

### Endpoint de Salud

Para comprobar si el servicio está activo.

```bash
curl http://localhost:8000/
```
**Respuesta esperada:** `{"status":"online","message":"TTS service is running","config":{"voice_sample":null,"language":"es"}}`

### Endpoint de Configuración (Optimización)

Establece parámetros por defecto (voz y/o idioma) para no tener que enviarlos en cada petición. Además, al establecer una voz, el sistema **pre-carga** sus embeddings en caché.

```bash
curl -X POST http://localhost:8000/api/config \
-H "Content-Type: application/json" \
-d 
'{
    "voice_sample": "my_voice_sample.wav",
    "language": "es"
}'
```

Una vez configurado, puedes enviar peticiones de síntesis enviando **solo el texto**:

```bash
curl -X POST http://localhost:8000/api/tts/batch \
-H "Content-Type: application/json" \
-d '{"text": "Hola, estoy usando la configuración por defecto."}' \
--output simple_output.wav
```

### Endpoint Batch


Genera un archivo de audio completo y lo guarda.

```bash
curl -X POST http://localhost:8000/api/tts/batch \
-H "Content-Type: application/json" \
-d 
'{
    "text": "Hola mundo, esta es una prueba de clonación de voz en modo batch.",
    "voice_sample": "my_voice_sample.mp3", # Puedes usar cualquier formato como .wav, .mp4, etc.
    "language": "es"
}' \
--output batch_output.wav
```
Este comando guardará la salida de audio en un archivo llamado `batch_output.wav` en tu directorio actual.

### Endpoint Streaming

Recibe los chunks de audio a medida que se generan. Es ideal para aplicaciones en tiempo real.

```bash
curl -X POST http://localhost:8000/api/tts/stream \
-H "Content-Type: application/json" \
-d 
'{
    "text": "Esta es una prueba de la API en modo streaming. El audio debería empezar a sonar casi de inmediato.",
    "voice_sample": "my_voice_sample.mp3", # Puedes usar cualquier formato como .wav, .mp4, etc.
    "language": "es"
}' \
--output stream_output.wav
```


### Cliente de Python (Streaming)

El proyecto incluye scripts de prueba en la carpeta `client_tests` que demuestran cómo consumir la API.

**Requisitos del cliente:**

```bash
cd client_tests
pip install -r requirements.txt
```

**Uso del cliente de streaming:**

```bash
python stream_client.py
```

El script te solicitará:
1.  **Nombre del archivo de voz:** (opcional) Si lo dejas vacío, usará el configurado por defecto en el servidor.
2.  **Texto:** (opcional) Si lo dejas vacío, usará un texto de prueba predefinido.

El audio generado se guardará como `stream_output.wav` y se reproducirá si tienes los drivers de audio configurados.
