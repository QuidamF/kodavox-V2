# Integración ElevenLabs STT (Scribe)

Esta rama `feature/elevenlabs-stt` contiene la integración completa del proveedor **ElevenLabs Speech-to-Text (Scribe)** dentro del motor y flujo orquestador de KodaVox.

## Variables de Entorno en `.env`

```env
# Clave API
ELEVENLABS_API_KEY=tu_api_key_aqui

# Configuración de Proveedor STT (whisper | elevenlabs)
STT_PROVIDER=elevenlabs
```

## Arquitectura y Componentes
1. `orchestrator/services/elevenlabs_stt.py`: Servicio `ElevenLabsSTTService` encargado de convertir audio PCM de voz (segmentado dinámicamente por Silero VAD) a formato WAV en memoria y realizar la solicitud HTTP/STT hacia ElevenLabs Scribe `/v1/speech-to-text`.
2. `orchestrator/core_engine.py`: Incorpora el selector `STT_PROVIDER`. Si está configurado en `elevenlabs`, conmuta la transcripción local de Whisper hacia la API cloud de ElevenLabs.
3. `scripts/test_elevenlabs_stt.py`: Script de prueba independiente para benchmark con audios de prueba local (`--file`).

## Cómo probar en el Motor Principal (KodaVox V2)

Para iniciar KodaVox utilizando ElevenLabs STT:

```bash
# Definir variable de entorno o ponerla en .env
export STT_PROVIDER=elevenlabs

# Ejecutar el motor
source /home/edgar-ld/Escritorio/venv/bin/activate
python3 orchestrator/core_engine.py
```
