"""Proveedor local Piper para síntesis rápida sin clonación de voz."""

from pathlib import Path
from typing import Optional

from piper import PiperVoice, SynthesisConfig


class PiperTTSService:
    """Carga una voz ONNX de Piper una sola vez y sintetiza PCM int16 mono."""

    def __init__(
        self,
        model_path: str,
        length_scale: float = 1.0,
        noise_scale: Optional[float] = None,
        speaker_id: Optional[int] = None,
    ):
        self.model_path = Path(model_path)
        self.length_scale = length_scale
        self.noise_scale = noise_scale
        self.speaker_id = speaker_id
        self.voice: Optional[PiperVoice] = None

    def load(self) -> None:
        """Carga el modelo, verificando que tanto el ONNX como su configuración existan."""
        config_path = Path(f"{self.model_path}.json")
        for path in (self.model_path, config_path):
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(
                    f"Modelo Piper inválido o ausente: {path}. "
                    "Descarga una voz con `python -m piper.download_voices`."
                )

        self.voice = PiperVoice.load(self.model_path)

    def synthesize(self, text: str) -> tuple[int, bytes]:
        """Devuelve audio PCM int16 mono y su frecuencia de muestreo."""
        if self.voice is None:
            self.load()

        synthesis_config = SynthesisConfig(
            speaker_id=self.speaker_id,
            length_scale=self.length_scale,
            noise_scale=self.noise_scale,
        )
        audio_chunks = list(self.voice.synthesize(text, syn_config=synthesis_config))
        if not audio_chunks:
            return self.voice.config.sample_rate, b""

        first_chunk = audio_chunks[0]
        if first_chunk.sample_width != 2 or first_chunk.sample_channels != 1:
            raise RuntimeError("Piper debe entregar PCM int16 mono para el reproductor actual.")

        return first_chunk.sample_rate, b"".join(chunk.audio_int16_bytes for chunk in audio_chunks)
