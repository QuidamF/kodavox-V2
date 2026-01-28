import pyaudio
import threading
import asyncio
import numpy as np
from typing import Callable, List
from config import Config
from core.event_bus import EventBus

class AudioCapturer:
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self._running = False
        self._thread = None
        self.loop = None
        
        self.p = pyaudio.PyAudio()
        self.stream = None
        
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = Config.SAMPLE_RATE
        self.chunk = Config.CHUNK_SIZE
        
        # Parámetros de detección de silencio
        # Parámetros de detección de silencio
        self.silence_threshold = Config.MIC_ENERGY_THRESHOLD  # Configurable
        self.dynamic_threshold = Config.MIC_DYNAMIC_ENERGY
        self.chunks_of_silence = 0
        self.max_silence_chunks = 20 # ~1.6s con chunks de 80ms

    def start(self, loop):
        if self._running:
            return

        self.loop = loop
        self._running = True
        self.stream = self.p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=Config.MICROPHONE_INDEX,
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
                audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                
                # Aplicar Ganancia Digital (Amplificar audio bajo)
                if Config.MIC_GAIN > 1.0:
                    audio_data = audio_data * Config.MIC_GAIN
                    # Clampear para evitar distorsión si se pasa de int16
                    audio_data = np.clip(audio_data, -32768, 32767)
                
                # Reconvertir a bytes para enviar al bus (si se modificó)
                if Config.MIC_GAIN > 1.0:
                    data = audio_data.astype(np.int16).tobytes()

                energy = np.sqrt(np.mean(audio_data**2))

                # DEBUG VISUAL: Imprimir nivel de energía cada 50 chunks (aprox 1 seg)
                self.chunks_of_silence += 1 # Usando este contador temporalmente para el print
                if self.chunks_of_silence % 20 == 0:
                     status = "🔴" if energy < self.silence_threshold else "🟢"
                     print(f"[Audio] Energy: {energy:.2f} | Threshold: {self.silence_threshold:.2f} {status}", end="\r")

                # Ajuste dinámico simple (si está activo)
                if self.dynamic_threshold:
                    if energy > self.silence_threshold * 2: 
                        # Si hay mucho ruido, subir umbral ligeramente
                        self.silence_threshold = min(self.silence_threshold * 1.01, 1000)
                    elif energy < self.silence_threshold * 0.5:
                        # Si hay silencio, bajar umbral (hasta un mínimo)
                        self.silence_threshold = max(self.silence_threshold * 0.99, 5) # Mínimo 5
                
                # Emitir evento de audio crudo de manera thread-safe
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.bus.emit("audio_chunk", {
                            "data": data,
                            "energy": float(energy)
                        }),
                        self.loop
                    )

            except Exception as e:
                print(f"[AudioCapturer] Error: {e}")
                break

    def terminate(self):
        self.stop()
        self.p.terminate()
