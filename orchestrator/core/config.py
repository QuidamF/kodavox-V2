import os

# --- Configuración Base y Muestreo de Audio ---
SAMPLE_RATE = 16000
CHUNK_SIZE = 512

# --- Proveedores e Invocación LLM ---
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

# --- Proveedor STT (Speech-to-Text) ---
STT_PROVIDER = os.getenv("STT_PROVIDER", "whisper").lower()
STT_MODEL = os.getenv("STT_MODEL", "small")
STT_BEAM_SIZE = int(os.getenv("STT_BEAM_SIZE", "5"))
STT_INITIAL_PROMPT = os.getenv("STT_INITIAL_PROMPT", "KodaVox, NextBeam")
STT_VAD_FILTER = os.getenv("STT_VAD_FILTER", "true").lower() == "true"
STT_CONDITION_ON_PREVIOUS_TEXT = os.getenv("STT_CONDITION_ON_PREVIOUS_TEXT", "false").lower() == "true"

# --- Modo de Interacción y Detección VAD ---
INTERACTION_MODE = os.getenv("INTERACTION_MODE", "active").lower()
WAKE_WORD = os.getenv("WAKE_WORD", "KodaVox")
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.60"))
VAD_END_SILENCE_SECONDS = float(os.getenv("VAD_END_SILENCE_SECONDS", "0.70"))
STT_MIN_SPEECH_SECONDS = float(os.getenv("STT_MIN_SPEECH_SECONDS", "0.60"))
VAD_PRE_PADDING_SECONDS = float(os.getenv("VAD_PRE_PADDING_SECONDS", "0.20"))
WAKE_SESSION_TIMEOUT_SECONDS = float(os.getenv("WAKE_SESSION_TIMEOUT_SECONDS", "10"))

# --- Proveedores TTS (Text-to-Speech) ---
TTS_URL = os.getenv("TTS_URI", "http://127.0.0.1:8001/api/tts/stream")
TTS_CONFIG_URL = os.getenv("TTS_CONFIG_URI", "http://127.0.0.1:8001/api/config")
TTS_HEALTH_URL = os.getenv("TTS_HEALTH_URL", "http://127.0.0.1:8001/")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "xtts").lower()

PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "models/es_MX-claude-high.onnx")
PIPER_LENGTH_SCALE = float(os.getenv("PIPER_LENGTH_SCALE", "1.0"))
PIPER_NOISE_SCALE = os.getenv("PIPER_NOISE_SCALE")
PIPER_SPEAKER_ID = os.getenv("PIPER_SPEAKER_ID")

CONFIGURE_TTS_VOICE_ON_START = os.getenv("TTS_CONFIGURE_VOICE_ON_START", "false").lower() == "true"
VOICE_SAMPLE = os.getenv("VOICE_SAMPLE")
