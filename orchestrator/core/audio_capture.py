import pyaudio
import threading
import numpy as np
from typing import Callable, List
from ..config import Config
from .event_bus import EventBus

class AudioCapturer:
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self._running = False
        self._thread = None
        
        self.p = pyaudio.PyAudio()
        self.stream = None
        
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = Config.SAMPLE_RATE
        self.chunk = Config.CHUNK_SIZE
        
        # Parámetros de detección de silencio
        self.silence_threshold = 500  # Ajustar según entorno
        self.chunks_of_silence = 0
        self.max_silence_chunks = 20 # ~1.6s con chunks de 80ms

    def start(self):
        if self._running:
            return

        self._running = True
        self.stream = self.p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[AudioCapturer] Started capturing audio and emitting events.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        print("[AudioCapturer] Stopped.")

    def _capture_loop(self):
        while self._running:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                
                # Calcular energía para detección de silencio/actividad
                audio_data = np.frombuffer(data, dtype=np.int16)
                energy = np.sqrt(np.mean(audio_data**2))
                
                # Emitir evento de audio crudo
                # Usamos schedule en el loop de eventos si es necesario, 
                # pero aquí emitimos directo al bus.
                self.bus.sio.start_background_task(self.bus.emit, "audio_chunk", {
                    "data": data,
                    "energy": float(energy)
                })

            except Exception as e:
                print(f"[AudioCapturer] Error: {e}")
                break

    def terminate(self):
        self.stop()
        self.p.terminate()
