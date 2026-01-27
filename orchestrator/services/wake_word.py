import numpy as np
from openwakeword.model import Model
import threading
from ..config import Config
from ..core.event_bus import EventBus
from ..core.state_manager import StateManager, AppState

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

    def start(self):
        self._active = True
        print("[WakeWordService] Active and listening for wake word.")

    def stop(self):
        self._active = False
        print("[WakeWordService] Paused.")

    def process_audio(self, audio_data: bytes):
        """Procesa stream de audio para detectar la wake word."""
        if not self._active:
            return

        # Solo procesar si estamos en estado IDLE o LISTENING_WAKEWORD
        current_state = self.state_manager.get_state()
        if current_state not in [AppState.IDLE, AppState.LISTENING_WAKEWORD]:
            return

        # Convertir bytes a numpy array
        audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
        
        # Predecir
        prediction = self.model.predict(audio_int16)
        
        # Verificar detección
        for md in self.model.prediction_buffer.keys():
            score = self.model.prediction_buffer[md][-1]
            if score > Config.WAKE_WORD_THRESHOLD:
                print(f"[WakeWordService] Wake Word Detected! ({score:.2f})")
                self.bus.emit("wakeword_detected", {"score": score})
                # Resetear buffer para evitar detecciones múltiples inmediatas
                self.model.reset()
