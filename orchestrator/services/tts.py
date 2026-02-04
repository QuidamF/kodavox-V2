import requests
import pyaudio
from config import Config

class TTSServiceAdapter:
    def __init__(self):
        self.uri = Config.TTS_URI
        self.p = pyaudio.PyAudio()

    def speak(self, text: str):
        """Envía texto al servicio TTS y reproduce el audio recibido."""
        if not text:
            return

        print(f"[TTSService] Speaking: {text[:30]}...")
        stream_gen = self.stream_audio(text)
        
        # Reproducir localmente mientras se consume el generador
        # Nota: Si el orquestador también consume este generador, necesitamos una forma de bifurcar el stream o 
        # el orquestador debe llamara a stream_audio directamente.
        # Por compatibilidad con código existente que llama a speak(), mantenemos reproducción local aquí
        # pero para el caso del dashboard, el orquestador llamará a stream_audio.
        
        try:
            self._play_from_generator(stream_gen)
        except Exception as e:
            print(f"[TTSService] Error playing audio: {e}")

    async def stream_audio_async(self, text: str):
        """Generador ASINCRONO que yielda chunks de audio desde el servicio TTS."""
        import httpx
        try:
            payload = {
                "text": text,
                "stream": True # Solicitamos stream al backend TTS
            }
            if Config.TTS_VOICE_FILE:
                payload["voice_sample"] = Config.TTS_VOICE_FILE
            
            chunk_count = 0
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", self.uri, json=payload, timeout=30.0) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        if chunk:
                            yield chunk
        except Exception as e:
             print(f"[TTSService] Error streaming audio (async): {e}")

    def stream_audio(self, text: str):
        """Generador que yielda chunks de audio desde el servicio TTS (SYNC - Requests)."""
        try:
            payload = {
                "text": text,
                "stream": True # Solicitamos stream al backend TTS
            }
            if Config.TTS_VOICE_FILE:
                payload["voice_sample"] = Config.TTS_VOICE_FILE
            
            chunk_count = 0
            with requests.post(self.uri, json=payload, stream=True) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        chunk_count += 1
                        yield chunk
            print(f"[TTSService] Stream finished. Yielded {chunk_count} chunks.")
        except Exception as e:
             print(f"[TTSService] Error streaming audio: {e}")

    def _play_from_generator(self, generator):
        """Reproduce audio desde un generador de chunks."""
        stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,
            output=True,
            output_device_index=Config.OUTPUT_DEVICE_INDEX
        )
        try:
            for chunk in generator:
                stream.write(chunk)
        finally:
            stream.stop_stream()
            stream.close()
