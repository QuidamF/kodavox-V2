import os
import httpx
from typing import AsyncGenerator

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsTTSService:
    """Servicio para la síntesis de voz en streaming utilizando ElevenLabs API."""

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)

    async def stream_audio_pcm(self, text: str) -> AsyncGenerator[bytes, None]:
        """Envía el texto a ElevenLabs y entrega fragmentos de audio PCM de 24kHz (16-bit mono)."""
        if not text:
            return

        if not self.api_key:
            print("[ElevenLabs Error] ELEVENLABS_API_KEY no configurada.")
            return

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream?output_format=pcm_24000"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/pcm",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, headers=headers, json=payload, timeout=30.0) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        print(f"[ElevenLabs Error] HTTP {response.status_code}: {error_body.decode('utf-8')}")
                        return

                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        if chunk:
                            yield chunk
        except Exception as error:
            print(f"[ElevenLabs Error] {error}")
