# 🎙️ KodaVox V2: Active Speech Engine

Bienvenido a **KodaVox V2**. Esta versión ha sido rediseñada desde cero para priorizar la **latencia mínima absoluta**, pasando de una arquitectura de microservicios distribuida a un **Motor Monolítico en Memoria** enfocado en una experiencia de "Habla Activa" (Active Speech) fluida.

## 🚀 Cambios Principales (V2)
- **Latencia Zero-Internal**: VAD y STT ahora corren en el mismo proceso de Python, eliminando saltos de red.
- **Barge-in Nativo**: El sistema detecta interrupciones de forma instantánea mediante Silero VAD local.
- **Desacoplamiento**: Se eliminaron dependencias de WakeWord y RAG para maximizar la velocidad de respuesta.
- **Dashboard de Diagnóstico**: Nueva interfaz en React/Vite para monitorear telemetría en tiempo real.

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
