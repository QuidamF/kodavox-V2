import asyncio
import numpy as np
import pyaudio
import torch

from core.config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    VAD_THRESHOLD,
    VAD_END_SILENCE_SECONDS,
    STT_MIN_SPEECH_SECONDS,
    VAD_PRE_PADDING_SECONDS,
    INTERACTION_MODE,
)

class AudioDriver:
    def __init__(self, engine_ref):
        self.engine = engine_ref
        self.pa = pyaudio.PyAudio()
        
        # VAD Model (Silero en CPU)
        print("[AudioDriver] Cargando modelo Silero VAD en CPU...")
        self.vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        self.vad_model.to("cpu")
        self.get_speech_timestamps = utils[0]
        
        self.stream = None
        self.audio_buffer = []
        self.pre_padding = []
        self.recording = False
        self.silence_samples = 0
        self.speech_samples = 0
        
    def start_microphone(self, callback):
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            stream_callback=callback
        )
        print("[AudioDriver] Micrófono Abierto.")
        self.stream.start_stream()

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pa.terminate()
