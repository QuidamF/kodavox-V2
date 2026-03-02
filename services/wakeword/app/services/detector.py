import numpy as np
from openwakeword.model import Model
import os

class WakeWordDetector:
    def __init__(self, model_name: str, threshold: float):
        self.model_name = model_name
        self.threshold = threshold
        
        print(f"[Detector] Loading model: {model_name}")
        try:
            self.model = Model(wakeword_models=[model_name], inference_framework="tflite")
        except Exception as e:
            print(f"[Detector] Failed to load '{model_name}': {e}. Falling back to 'alexa'.")
            self.model = Model(wakeword_models=["alexa"], inference_framework="tflite")
        
        self.cooldown = 0
        self.cooldown_frames = 20 # ~1.6s @ 80ms chunks

    def process_frame(self, audio_data: bytes) -> bool:
        """Processes a single frame of audio and returns True if detected."""
        if self.cooldown > 0:
            self.cooldown -= 1
            return False

        # Convert bytes to numpy int16
        audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
        
        # Predict
        self.model.predict(audio_int16)
        
        # Check scores
        for md in self.model.prediction_buffer.keys():
            score = self.model.prediction_buffer[md][-1]
            if score > self.threshold:
                print(f"[Detector] Detected! ({score:.2f})")
                self.cooldown = self.cooldown_frames
                self.model.reset()
                return True
        
        return False

    def reset(self):
        self.model.reset()
        self.cooldown = 0
