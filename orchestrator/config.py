import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Service URLs (External mapping from Docker Compose)
    STT_URI = os.getenv("STT_URI", "ws://localhost:8000/api/v1/streaming")
    TTS_URI = os.getenv("TTS_URI", "http://localhost:8001/api/tts/stream")
    RAG_URI = os.getenv("RAG_URI", "http://localhost:8002/ask")

    # Wake Word (Local runtime)
    WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
    WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))

    # Audio Settings
    SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1280"))
    MICROPHONE_INDEX = int(os.getenv("MICROPHONE_INDEX", "1"))
    OUTPUT_DEVICE_INDEX = int(os.getenv("OUTPUT_DEVICE_INDEX", "4"))
    
    # Mic Sensitivity
    MIC_ENERGY_THRESHOLD = int(os.getenv("MIC_ENERGY_THRESHOLD", "300"))
    MIC_DYNAMIC_ENERGY = os.getenv("MIC_DYNAMIC_ENERGY", "false").lower() == "true"
    MIC_GAIN = float(os.getenv("MIC_GAIN", "1.0"))

    # TTS Settings
    TTS_VOICE_FILE = os.getenv("TTS_VOICE_FILE", os.getenv("VOICE_SAMPLE", ""))
