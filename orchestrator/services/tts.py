import requests
import pyaudio
from ..config import Config

class TTSServiceAdapter:
    def __init__(self):
        self.uri = Config.TTS_URI
        self.p = pyaudio.PyAudio()

    def speak(self, text: str):
        """Envía texto al servicio TTS y reproduce el audio recibido."""
        if not text:
            return

        print(f"[TTSService] Speaking: {text[:30]}...")
        try:
            payload = {
                "text": text,
                "stream": True
            }
            if Config.TTS_VOICE_FILE:
                payload["voice_sample"] = Config.TTS_VOICE_FILE
            # Puede ser endpoint de stream o batch. Config apunta a stream.
            
            with requests.post(self.uri, json=payload, stream=True) as response:
                response.raise_for_status()
                self._play_stream(response)
                
        except Exception as e:
            print(f"[TTSService] Error: {e}")

    def _play_stream(self, response):
        """Reproduce el stream de audio chunk por chunk."""
        # Asumiendo formato WAV/PCM compatible.
        # En una implementación real robusta, se debería parsear el header WAV 
        # o usar ffmpeg para decodificar al vuelo si es MP3/Opus.
        # Por simplicidad y asumiendo servicio local devuelve WAV stream:
        
        stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000, # XTTS suele ser 24k
            output=True
        )

        try:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    stream.write(chunk)
        finally:
            stream.stop_stream()
            stream.close()
