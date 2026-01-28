import numpy as np
from openwakeword.model import Model
import threading
from config import Config
from core.event_bus import EventBus
from core.state_manager import StateManager, AppState

class WakeWordService:
    def __init__(self, event_bus: EventBus, state_manager: StateManager):
        self.bus = event_bus
        self.state_manager = state_manager
        self._active = False
        
        # Cargar modelo (descarga automática si no existe)
        print(f"[WakeWordService] Loading model: {Config.WAKE_WORD_MODEL}")
        try:
            self.model = Model(wakeword_models=[Config.WAKE_WORD_MODEL], inference_framework="onnx")
        except Exception as e:
            print(f"[WakeWordService] Failed to load specific model, falling back/error: {e}")
            # Fallback a un modelo por defecto si falla
            self.model = Model() 
        
        self.cooldown = 0
        self.cooldown_frames = 25 # ~2 segundos con chunks de 80ms 

    def start(self):
        self._active = True
        print("[WakeWordService] Active and listening for wake word.")

    def stop(self):
        self._active = False
        print("[WakeWordService] Paused.")

    async def process_audio(self, audio_data: bytes):
        """Procesa stream de audio para detectar la wake word."""
        if not self._active:
            return

        # Solo procesar si estamos en estado IDLE o LISTENING_WAKEWORD
        current_state = self.state_manager.get_state()
        if current_state not in [AppState.IDLE, AppState.LISTENING_WAKEWORD]:
            return

        if self.cooldown > 0:
            # print(f"[WakeWordService] Cooldown active: {self.cooldown}") # Commented to avoid flooding 
            self.cooldown -= 1
            return
        
        # print("[WakeWordService] Processing frame...") # Debug flow

        # Convertir bytes a numpy array
        audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
        
        # Predecir (Running in thread executor to avoid blocking loop if slow)
        # Note: openwakeword is fast, but better safe. For now keeping simple sync execution 
        # unless user reports lag.
        prediction = self.model.predict(audio_int16)
        
        # Verificar detección
        for md in self.model.prediction_buffer.keys():
            score = self.model.prediction_buffer[md][-1]
            if score > Config.WAKE_WORD_THRESHOLD:
                print(f"[WakeWordService] Wake Word Detected! ({score:.2f})")
                
                # IMPORTANT: Set cooldown BEFORE emitting to prevent race condition
                # where subsequent audio chunks trigger detection while emit is awaiting.
                self.cooldown = self.cooldown_frames
                
                print(f"[WakeWordService] Emitting event... (Cooldown set to {self.cooldown})")
                await self.bus.emit("wakeword_detected", {"score": float(score)})
                print("[WakeWordService] Event emitted.")
                
                # Resetear buffer
                self.model.reset()
