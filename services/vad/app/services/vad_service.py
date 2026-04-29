import torch
import numpy as np

try:
    from silero_vad import load_silero_vad, VADIterator
    model = load_silero_vad()
    vad_iterator = VADIterator(model)
    has_vad = True
except ImportError:
    has_vad = False

class SileroVADService:
    def __init__(self):
        self.in_speech = False
        self.buffer = np.array([], dtype=np.float32)
        if has_vad:
            self.iterator = vad_iterator
        else:
            self.iterator = None

    async def process_chunk(self, audio_chunk: bytes) -> list[dict]:
        """
        Procesa un chunk de audio y retorna una lista de eventos generados.
        """
        events = []
        if not self.iterator:
            return events

        # Convertir bytes (PCM int16) a float32 y añadir al buffer
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        self.buffer = np.concatenate((self.buffer, audio_data))

        while len(self.buffer) >= 512:
            chunk = self.buffer[:512]
            self.buffer = self.buffer[512:]
            
            tensor_chunk = torch.from_numpy(chunk)
            # Iterar el VAD con el chunk de 512
            speech_dict = self.iterator(tensor_chunk, return_seconds=True)

            if speech_dict:
                if 'start' in speech_dict and not self.in_speech:
                    self.in_speech = True
                    events.append({"type": "speech_start"})
                elif 'end' in speech_dict and self.in_speech:
                    self.in_speech = False
                    events.append({"type": "speech_end"})

        if self.in_speech:
            events.append({"type": "speech_frame", "data": audio_chunk})

        return events
