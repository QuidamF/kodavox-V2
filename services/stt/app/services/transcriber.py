import asyncio
import os
from functools import partial
from faster_whisper import WhisperModel
from app.core.config import settings
from app.database import get_config

class TranscriberService:
    def __init__(self):
        self.model_size = settings.MODEL_SIZE
        self.device = settings.DEVICE
        self.compute_type = "default"
        self.models_dir = settings.MODELS_DIR
        
        # Load configuration from database
        config = get_config()
        self.language = config.get('language') if config else None
        self.beam_size = config.get('beam_size', 5) if config else 5

        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)

        print(f"Loading Whisper model: {self.model_size} on {self.device}...")
        self.model = WhisperModel(
            self.model_size, 
            device=self.device, 
            compute_type=self.compute_type,
            download_root=self.models_dir
        )
        print("Whisper model loaded successfully.")

    def _transcribe_sync(self, file_path: str) -> str:
        """
        Synchronous wrapper for the blocking transcribe method.
        """
        segments, info = self.model.transcribe(
            file_path,
            beam_size=self.beam_size,
            language=self.language
        )

        if self.language:
            print(f"Specified language: '{self.language}'")
        else:
            print(f"Detected language: '{info.language}' with probability {info.language_probability}")

        transcription = "".join(segment.text for segment in segments)
        return transcription.strip()

    async def transcribe_file(self, file_path: str) -> str:
        """
        Asynchronous wrapper that runs the blocking transcription in a separate thread.
        """
        loop = asyncio.get_running_loop()
        # Run the synchronous method in a thread pool to avoid blocking the event loop
        return await loop.run_in_executor(
            None, 
            partial(self._transcribe_sync, file_path)
        )

# Global instance
_transcriber_instance = None

def get_transcriber_service() -> TranscriberService:
    global _transcriber_instance
    if _transcriber_instance is None:
        _transcriber_instance = TranscriberService()
    return _transcriber_instance

def update_transcriber_config(data: dict):
    """Update the transcriber configuration in memory."""
    global _transcriber_instance
    if _transcriber_instance:
        if 'language' in data:
            _transcriber_instance.language = data['language']
        if 'beam_size' in data:
            _transcriber_instance.beam_size = data['beam_size']
