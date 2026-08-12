import os
import httpx
import json
import base64
import asyncio
from typing import AsyncGenerator
import websockets
from .usage_tracker import tracker

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsTTSService:
    """Servicio para la síntesis de voz en streaming utilizando ElevenLabs API."""

    def __init__(self, voice_id: str = None):
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)
        self.stability = 0.5
        self.similarity_boost = 0.75
        self.style = 0.0
        self.use_speaker_boost = True

    def update_settings(self, stability: float, similarity_boost: float, style: float, use_speaker_boost: bool):
        self.stability = stability
        self.similarity_boost = similarity_boost
        self.style = style
        self.use_speaker_boost = use_speaker_boost

    async def stream_audio_pcm(self, text: str) -> AsyncGenerator[bytes, None]:
        """Envía el texto a ElevenLabs por HTTP y entrega fragmentos de audio PCM de 24kHz (16-bit mono)."""
        if not text:
            return
            
        tracker.add_elevenlabs_chars(len(text))

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
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
                "style": self.style,
                "use_speaker_boost": self.use_speaker_boost
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

    async def stream_input_pcm(self, text_iterator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """Envía texto token a token por WebSocket (Input Streaming) y devuelve audio PCM de 24kHz en tiempo real."""
        if not self.api_key:
            print("[ElevenLabs Error] ELEVENLABS_API_KEY no configurada.")
            return

        url = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream-input?model_id={self.model_id}&output_format=pcm_24000"

        try:
            async with websockets.connect(url) as websocket:
                # 1. Enviar payload inicial (BOS)
                bos_message = {
                    "text": " ",
                    "voice_settings": {
                        "stability": self.stability,
                        "similarity_boost": self.similarity_boost,
                        "style": self.style,
                        "use_speaker_boost": self.use_speaker_boost
                    },
                    "xi_api_key": self.api_key,
                }
                await websocket.send(json.dumps(bos_message))

                # 2. Tarea para enviar texto (sender)
                async def sender():
                    char_count = 0
                    try:
                        async for token in text_iterator:
                            if token:
                                char_count += len(token)
                                await websocket.send(json.dumps({"text": token}))
                        # Enviar EOS
                        await websocket.send(json.dumps({"text": ""}))
                        if char_count > 0:
                            tracker.add_elevenlabs_chars(char_count)
                    except Exception as e:
                        print(f"[ElevenLabs Sender Error] {e}")

                sender_task = asyncio.create_task(sender())

                # 3. Leer y devolver audio (receiver)
                try:
                    while True:
                        response = await websocket.recv()
                        data = json.loads(response)
                        
                        if data.get("audio"):
                            audio_bytes = base64.b64decode(data["audio"])
                            yield audio_bytes
                            
                        if data.get("isFinal"):
                            break
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    print(f"[ElevenLabs Receiver Error] {e}")
                finally:
                    if not sender_task.done():
                        sender_task.cancel()
                        
        except Exception as error:
            print(f"[ElevenLabs WS Error] {error}")
