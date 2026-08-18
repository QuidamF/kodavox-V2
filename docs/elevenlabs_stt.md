# Integración ElevenLabs STT (Scribe)

Esta rama `feature/elevenlabs-stt` contiene los componentes para evaluar y consumir la API de **ElevenLabs Speech-to-Text (Scribe)**.

## Archivos Creados
1. `orchestrator/services/elevenlabs_stt.py`: Servicio `ElevenLabsSTTService` encargado de convertir audio PCM/WAV y consumir el endpoint de ElevenLabs `/v1/speech-to-text`.
2. `scripts/test_elevenlabs_stt.py`: Script de prueba autónomo para validar el tiempo de respuesta y la precisión de la transcripción.

## Requisitos de Configuración
Asegúrate de contar con tu clave de API en tu archivo `.env` o variable de entorno:
```env
ELEVENLABS_API_KEY=tu_api_key_aqui
```

## Ejemplo de Uso

```python
from services.elevenlabs_stt import ElevenLabsSTTService

stt_service = ElevenLabsSTTService()
# audio_pcm es un buffer de bytes PCM (ejemplo: 16kHz, 16-bit mono)
text = await stt_service.transcribe_audio_bytes(audio_pcm, sample_rate=16000, language_code="spa")
print("Transcripción:", text)
```

## Script de Prueba
Puedes ejecutar la prueba con:
```bash
python3 scripts/test_elevenlabs_stt.py
```
