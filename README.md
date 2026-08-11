# 🎙️ KodaVox V2: Active Speech Engine

Bienvenido a **KodaVox V2**. Esta versión ha sido rediseñada desde cero para priorizar la **latencia mínima absoluta**, pasando de una arquitectura de microservicios distribuida a un **Motor Monolítico en Memoria** enfocado en una experiencia de "Habla Activa" (Active Speech) fluida.

## 🚀 Nuevas Funciones y Arquitectura (V2.1)
- **Latencia Zero-Internal**: VAD y STT ahora corren en el mismo proceso de Python, eliminando saltos de red.
- **Barge-in Nativo**: El sistema detecta interrupciones de forma instantánea mediante Silero VAD local.
- **RAG y WakeWord nativos**: Se reintegraron en el core monolítico con soporte dinámico.
- **Motor Headless (Socket.IO)**: Telemetría en tiempo real y transmisión de audio crudo por WebSocket.
- **Sincronización con Robot Face**: Integración nativa (vía WS 8760) para controlar animaciones faciales y lip-sync (loopback).
- **Control de Costos**: Módulo integrado para rastrear el consumo de tokens y caracteres en proveedores como OpenAI, Gemini y ElevenLabs.
- **Dashboard de Diagnóstico Extendido**: Nueva interfaz en React/Vite para monitorear telemetría, salud de hardware, costos y estado de la IA en tiempo real.

---

## 🛠️ Requisitos de Instalación (Ubuntu 22.04)

Para que el motor pueda compilar las librerías de audio nativas en Linux, debes instalar las dependencias de desarrollo de PortAudio:

```bash
# 1. Instalar dependencias del sistema (CRUCIAL)
sudo apt-get update && sudo apt-get install -y portaudio19-dev python3-dev build-essential

# 2. Asegúrate de tener Docker y NVIDIA Container Toolkit instalados para el TTS
```

---

## ⚡ Inicio Rápido

He creado un script de automatización que levanta todo el entorno (Docker, Venv, Motor y Dashboard) con un solo comando:

```bash
./start_v2.sh
```

### ¿Qué hace este script?
1. Levanta el contenedor de **XTTS (TTS)** en Docker.
2. Crea y configura un entorno virtual de Python (`venv`) en la carpeta `orchestrator/`.
3. Instala los requerimientos (`pyaudio`, `faster-whisper`, `torch`, etc.).
4. Inicia el **Motor Monolítico** (`core_engine.py`) en el puerto 5000.
5. Inicia el **Dashboard V2** en el puerto 5173.

---

## 📊 Dashboard de Diagnóstico
Una vez iniciado, abre tu navegador en:
👉 **http://localhost:5173**

Desde aquí podrás validar módulo por módulo:
- **Mic Level**: Nivel de entrada de audio.
- **VAD Status**: Detección de voz en tiempo real.
- **STT**: Transcripción inmediata de Whisper.
- **LLM**: Flujo de tokens de Ollama.
- **TTS**: Estado de la síntesis de voz.

---

## 👥 Notas de Desarrollo
- El motor se comunica con **Ollama** en `http://127.0.0.1:11434`. Asegúrate de tener Ollama corriendo localmente con el modelo configurado (por defecto `qwen2.5:3b`).
- La configuración principal reside en el archivo `.env` en la raíz.
- La voz de XTTS se conserva en la configuración persistente del servicio, para reutilizar sus latentes. Para forzar otra voz al iniciar, define `TTS_CONFIGURE_VOICE_ON_START=true` y `VOICE_SAMPLE=<archivo.wav>` en `.env`.
- Puedes seleccionar `TTS_PROVIDER=xtts`, `TTS_PROVIDER=piper` u `off`. Piper usa por defecto `models/es_MX-claude-high.onnx`, no requiere GPU ni clonación y admite ajustar la velocidad con `PIPER_LENGTH_SCALE`.
- La precisión de STT se controla con `STT_MODEL` (`small` o `medium`), `STT_INITIAL_PROMPT`, `STT_VAD_FILTER` y `STT_CONDITION_ON_PREVIOUS_TEXT`. `medium` requiere más VRAM y suele aportar mejor precisión en español.
- `INTERACTION_MODE=active` responde a cada intervención detectada por VAD. `INTERACTION_MODE=wakeword` exige que la transcripción contenga `WAKE_WORD` (por defecto `KodaVox`); puedes decir “KodaVox, ¿qué hora es?” o decir primero “KodaVox” y hacer la consulta en el siguiente turno. Tras responder, la sesión permanece abierta durante `WAKE_SESSION_TIMEOUT_SECONDS` (10 por defecto); después vuelve a requerir la frase de activación. `VAD_THRESHOLD`, `VAD_END_SILENCE_SECONDS` y `STT_MIN_SPEECH_SECONDS` controlan la sensibilidad.

---

## 🤖 Integración con Robot Face (Avatar)
KodaVox V2 incluye soporte nativo para el proyecto **Robot Face (OctopID)**. KodaVox actúa como el "cerebro" y controla directamente las expresiones y el lip-sync de la cara.

Para usarlo:
1. Inicia tu backend original de Robot Face (`audioServer.py` y `app_fastapi.py`).
2. Abre tu interfaz `face.html`.
3. En el Dashboard V2 de KodaVox, ve a la pestaña **Diagnósticos**.
4. Activa la opción **Sincronización de Estados (Robot Face)**.
*La sincronización labial (Lip-Sync) funcionará de forma automática ya que tu `audioServer.py` escucha la salida nativa de KodaVox mediante loopback de sistema.*

## 💰 Sistema de Costos
El motor guarda diariamente los consumos en `orchestrator/data/usage_stats.json`. En la pestaña de **Proveedores** del Dashboard puedes configurar cuánto pagas por Millón de tokens/caracteres, y KodaVox calculará tu gasto del día en tiempo real.
