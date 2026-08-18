import os
import httpx
import logging
import wave
import io
from typing import Optional

logger = logging.getLogger(__name__)

class ElevenLabsSTTService:
    """Servicio para la transcripción de audio (Speech-to-Text) utilizando la API de ElevenLabs (Scribe)."""

    def __init__(self, api_key: Optional[str] = None, model_id: str = "scribe_v1"):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "")
        self.model_id = model_id
        self.url = "https://api.elevenlabs.io/v1/speech-to-text"

    async def transcribe_audio_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
        language_code: Optional[str] = "spa"
    ) -> str:
        """
        Transcripción síncrona/batch enviando buffer de audio PCM formateado a WAV a ElevenLabs STT.
        """
        if not self.api_key:
            logger.error("[ElevenLabs STT] ELEVENLABS_API_KEY no configurada.")
            return ""

        if not audio_data:
            return ""

        # Convertir bytes raw PCM a contenedor WAV en memoria
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        wav_bytes = wav_buffer.getvalue()

        headers = {
            "xi-api-key": self.api_key
        }

        data = {
            "model_id": self.model_id
        }
        if language_code:
            data["language_code"] = language_code

        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav")
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=30.0
                )

                if response.status_code == 200:
                    res_json = response.json()
                    transcription = res_json.get("text", "")
                    logger.info(f"[ElevenLabs STT] Transcripción obtenida: {transcription}")
                    return transcription
                else:
                    logger.error(f"[ElevenLabs STT Error] HTTP {response.status_code}: {response.text}")
                    return ""
        except Exception as e:
            logger.error(f"[ElevenLabs STT Exception] {e}")
            return ""
