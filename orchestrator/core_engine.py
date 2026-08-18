import asyncio
import os
import torch
import numpy as np
import pyaudio
import httpx
import socketio
import uvicorn
import json
import sys
import re
import unicodedata
import websockets
import shutil
import zipfile
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from services.llm_provider import LLMFactory, DEFAULT_SYSTEM_PROMPT
from services.usage_tracker import tracker
import httpx

# --- Configuración Base ---
SAMPLE_RATE = 16000
CHUNK_SIZE = 512
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
STT_PROVIDER = os.getenv("STT_PROVIDER", "whisper").lower()
STT_MODEL = os.getenv("STT_MODEL", "small")
STT_BEAM_SIZE = int(os.getenv("STT_BEAM_SIZE", "5"))
STT_INITIAL_PROMPT = os.getenv("STT_INITIAL_PROMPT", "KodaVox, NextBeam")
STT_VAD_FILTER = os.getenv("STT_VAD_FILTER", "true").lower() == "true"
STT_CONDITION_ON_PREVIOUS_TEXT = os.getenv("STT_CONDITION_ON_PREVIOUS_TEXT", "false").lower() == "true"
INTERACTION_MODE = os.getenv("INTERACTION_MODE", "active").lower()
WAKE_WORD = os.getenv("WAKE_WORD", "KodaVox")
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.60"))
VAD_END_SILENCE_SECONDS = float(os.getenv("VAD_END_SILENCE_SECONDS", "0.70"))
STT_MIN_SPEECH_SECONDS = float(os.getenv("STT_MIN_SPEECH_SECONDS", "0.60"))
VAD_PRE_PADDING_SECONDS = float(os.getenv("VAD_PRE_PADDING_SECONDS", "0.20"))
WAKE_SESSION_TIMEOUT_SECONDS = float(os.getenv("WAKE_SESSION_TIMEOUT_SECONDS", "10"))
TTS_URL = os.getenv("TTS_URI", "http://127.0.0.1:8001/api/tts/stream")
TTS_CONFIG_URL = os.getenv("TTS_CONFIG_URI", "http://127.0.0.1:8001/api/config")
TTS_HEALTH_URL = os.getenv("TTS_HEALTH_URL", "http://127.0.0.1:8001/")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "xtts").lower()
PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "models/es_MX-claude-high.onnx")
PIPER_LENGTH_SCALE = float(os.getenv("PIPER_LENGTH_SCALE", "1.0"))
PIPER_NOISE_SCALE = os.getenv("PIPER_NOISE_SCALE")
PIPER_SPEAKER_ID = os.getenv("PIPER_SPEAKER_ID")
# La voz se gestiona y persiste en el servicio TTS. Solo se reemplaza al
# habilitar explícitamente esta opción para evitar recalcular latentes al inicio.
CONFIGURE_TTS_VOICE_ON_START = os.getenv("TTS_CONFIGURE_VOICE_ON_START", "false").lower() == "true"
VOICE_SAMPLE = os.getenv("VOICE_SAMPLE")

# --- Servidor de Telemetría (Socket.IO) ---
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

class MonolithicEngine:
    def __init__(self):
        print("[Engine] Inicializando Motor Monolítico KodaVox V2...")
        
        # 1. PyAudio
        self.pa = pyaudio.PyAudio()
        
        # 2. VAD (Silero) - Lo dejamos en CPU ya que es muy ligero y ahorramos VRAM
        print("[Engine] Cargando modelo Silero VAD en CPU...")
        self.vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        self.vad_model.to("cpu")
        self.get_speech_timestamps = utils[0]
        
        # 3. STT (Whisper o ElevenLabs)
        self.stt_provider = STT_PROVIDER
        self.stt_model = None
        self.elevenlabs_stt = None
        
        if self.stt_provider == "elevenlabs":
            from services.elevenlabs_stt import ElevenLabsSTTService
            print("[Engine] Usando ElevenLabs STT (Scribe cloud)...", flush=True)
            self.elevenlabs_stt = ElevenLabsSTTService()
        else:
            print(f"[Engine] Cargando modelo Whisper {STT_MODEL} en GPU (Modo ultra-eficiente int8_float16)...", flush=True)
            from faster_whisper import WhisperModel
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "int8_float16" if device == "cuda" else "int8"
            self.stt_model = WhisperModel(STT_MODEL, device=device, compute_type=compute_type)
        
        self.stt_prompt = STT_INITIAL_PROMPT
        
        self.is_speaking = False
        self.audio_buffer = []
        self.pre_padding = [] 
        self.recording = False
        self.silence_samples = 0
        self.speech_samples = 0
        self.is_processing = False
        self.conversation_history = []
        self.awaiting_user_query = False
        self.wake_session_active = False
        self.wake_session_token = 0
        self.wake_session_timeout_task = None
        self.loop = None
        self.vad_threshold = VAD_THRESHOLD
        self.interaction_mode = INTERACTION_MODE
        if self.interaction_mode not in ["active", "wakeword"]:
            print(f"[Engine] INTERACTION_MODE inválido: {INTERACTION_MODE}. Usando active.", flush=True)
        print(f"[Engine] Modo de interacción: {self.interaction_mode}. Umbral VAD: {self.vad_threshold}.", flush=True)
        self.piper_tts = None
        self.elevenlabs_tts = None
        
        # RAG Local Inicialización (Lazy Loaded)
        self.rag_service = None
        self.active_rag_collection = ""
        
        self.engine_state = "idle" # idle, listening, processing, speaking
        
        self._load_engine_state()
        if self.active_rag_collection:
            from services.rag_chroma import ChromaRAGService
            self.rag_service = ChromaRAGService()
            print(f"[Engine] RAG Activado con colección: {self.active_rag_collection}")
            
        self.llm_provider = LLMFactory.get_provider()
        print(f"[Engine] Proveedor LLM inicializado: {self.llm_provider.provider_name} ({self.llm_provider.model_name}).")

    def _load_engine_state(self):
        state_path = os.path.join(os.path.dirname(__file__), "data", "engine_state.json")
        try:
            if os.path.exists(state_path):
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    self.active_rag_collection = state.get("active_rag_collection", os.getenv("RAG_ACTIVE_COLLECTION", ""))
                    self.personality_prompt = state.get("personality_prompt", DEFAULT_SYSTEM_PROMPT)
                    
                    default_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
                    self.elevenlabs_voices = state.get("elevenlabs_voices", [{"name": "Default (Env)", "id": default_voice_id}])
                    self.active_voice_id = state.get("active_voice_id", default_voice_id)
                    self.voice_stability = state.get("voice_stability", 0.5)
                    self.voice_similarity_boost = state.get("voice_similarity_boost", 0.75)
                    self.voice_style = state.get("voice_style", 0.0)
                    self.voice_use_speaker_boost = state.get("voice_use_speaker_boost", True)
                    self.wake_word = state.get("wake_word", os.getenv("WAKE_WORD", "KodaVox"))
                    self.wake_session_timeout = state.get("wake_session_timeout", int(float(os.getenv("WAKE_SESSION_TIMEOUT_SECONDS", "10"))))
                    self.native_audio_output = state.get("native_audio_output", True)
                    self.robot_face_sync = state.get("robot_face_sync", False)
            else:
                self.active_rag_collection = os.getenv("RAG_ACTIVE_COLLECTION", "")
                self.personality_prompt = DEFAULT_SYSTEM_PROMPT
                default_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
                self.elevenlabs_voices = [{"name": "Default (Env)", "id": default_voice_id}]
                self.active_voice_id = default_voice_id
                self.voice_stability = 0.5
                self.voice_similarity_boost = 0.75
                self.voice_style = 0.0
                self.voice_use_speaker_boost = True
                self.wake_word = os.getenv("WAKE_WORD", "KodaVox")
                self.wake_session_timeout = int(float(os.getenv("WAKE_SESSION_TIMEOUT_SECONDS", "10")))
                self.native_audio_output = True
                self.robot_face_sync = False
        except Exception as e:
            print(f"[Engine] Error cargando estado: {e}")
            self.active_rag_collection = os.getenv("RAG_ACTIVE_COLLECTION", "")
            self.personality_prompt = DEFAULT_SYSTEM_PROMPT
            default_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            self.elevenlabs_voices = [{"name": "Default (Env)", "id": default_voice_id}]
            self.active_voice_id = default_voice_id
            self.voice_stability = 0.5
            self.voice_similarity_boost = 0.75
            self.voice_style = 0.0
            self.voice_use_speaker_boost = True
            self.wake_word = os.getenv("WAKE_WORD", "KodaVox")
            self.wake_session_timeout = int(float(os.getenv("WAKE_SESSION_TIMEOUT_SECONDS", "10")))
            self.native_audio_output = True
            self.robot_face_sync = False

    def _update_elevenlabs_settings(self):
        if getattr(self, 'elevenlabs_tts', None) is not None:
            self.elevenlabs_tts.update_settings(
                stability=getattr(self, 'voice_stability', 0.5),
                similarity_boost=getattr(self, 'voice_similarity_boost', 0.75),
                style=getattr(self, 'voice_style', 0.0),
                use_speaker_boost=getattr(self, 'voice_use_speaker_boost', True)
            )

    def _save_engine_state(self):
        state_path = os.path.join(os.path.dirname(__file__), "data", "engine_state.json")
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({
                    "active_rag_collection": self.active_rag_collection,
                    "personality_prompt": self.personality_prompt,
                    "elevenlabs_voices": self.elevenlabs_voices,
                    "active_voice_id": self.active_voice_id,
                    "voice_stability": getattr(self, 'voice_stability', 0.5),
                    "voice_similarity_boost": getattr(self, 'voice_similarity_boost', 0.75),
                    "voice_style": getattr(self, 'voice_style', 0.0),
                    "voice_use_speaker_boost": getattr(self, 'voice_use_speaker_boost', True),
                    "wake_word": self.wake_word,
                    "wake_session_timeout": self.wake_session_timeout,
                    "native_audio_output": self.native_audio_output,
                    "robot_face_sync": getattr(self, 'robot_face_sync', False)
                }, f, indent=4)
        except Exception as e:
            print(f"[Engine] Error guardando estado: {e}")

    async def setup_tts(self):
        if TTS_PROVIDER == "off":
            print("[Engine] TTS desactivado (TTS_PROVIDER=off).")
            return

        if TTS_PROVIDER == "piper":
            try:
                self.piper_tts = PiperTTSService(
                    PIPER_MODEL_PATH,
                    length_scale=PIPER_LENGTH_SCALE,
                    noise_scale=float(PIPER_NOISE_SCALE) if PIPER_NOISE_SCALE else None,
                    speaker_id=int(PIPER_SPEAKER_ID) if PIPER_SPEAKER_ID else None,
                )
                await asyncio.to_thread(self.piper_tts.load)
                print(f"[Engine] Piper listo: {PIPER_MODEL_PATH}.")
            except Exception as error:
                self.piper_tts = None
                print(f"[Engine] No se pudo cargar Piper: {error}")
            return

        if TTS_PROVIDER == "elevenlabs":
            try:
                self.elevenlabs_tts = ElevenLabsTTSService()
                self._update_elevenlabs_settings()
                print(f"[Engine] ElevenLabs listo (Voice ID: {self.elevenlabs_tts.voice_id}).")
            except Exception as error:
                self.elevenlabs_tts = None
                print(f"[Engine] No se pudo inicializar ElevenLabs: {error}")
            return

        if TTS_PROVIDER != "xtts":
            print(f"[Engine] TTS_PROVIDER inválido: {TTS_PROVIDER}. Usa xtts, piper, elevenlabs u off.")
            return

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(TTS_HEALTH_URL, timeout=15.0)
                response.raise_for_status()
                active_voice = response.json().get("config", {}).get("voice_sample", "sin configurar")

                if not CONFIGURE_TTS_VOICE_ON_START:
                    print(f"[Engine] TTS listo; conservando voz persistida: {active_voice}.")
                    return

                if not VOICE_SAMPLE:
                    print("[Engine] TTS listo; no se cambió la voz porque VOICE_SAMPLE no está definido.")
                    return

                payload = {"voice_sample": VOICE_SAMPLE, "language": "es"}
                response = await client.post(TTS_CONFIG_URL, json=payload, timeout=15.0)
                response.raise_for_status()
                print(f"[Engine] TTS configurado explícitamente con la voz: {VOICE_SAMPLE}.")
        except httpx.HTTPError as error:
            print(f"[Engine] No se pudo configurar el servicio TTS: {error}")

    async def emit_telemetry(self, event: str, data: dict):
        await sio.emit(event, data)

    async def _set_engine_state(self, new_state: str):
        self.engine_state = new_state
        await self.emit_telemetry('telemetry_state', {
            "state": self.engine_state,
            "session_active": self.wake_session_active
        })
        
        # Robot Face WS Sync
        if getattr(self, 'robot_face_sync', False):
            # Si estamos en modo wakeword y la sesión está inactiva, forzamos estado de reposo (Neutral)
            if self.interaction_mode == "wakeword" and not self.wake_session_active:
                mood = "Neutral"
            else:
                mood_map = {
                    "idle": "Alerta" if self.wake_session_active else "Neutral",
                    "listening": "Escuchando",
                    "processing": "Pensando",
                    "speaking": "Feliz"
                }
                mood = mood_map.get(new_state, "Neutral")
            try:
                # Fire and forget WS message directly to avoid blocking
                asyncio.create_task(self._send_robot_face_mood(mood))
            except Exception as e:
                pass

    async def _send_robot_face_mood(self, mood: str):
        try:
            async with websockets.connect("ws://localhost:8760", open_timeout=1) as ws:
                payload = json.dumps({"type": "mood", "mood": mood})
                await ws.send(payload)
        except Exception:
            pass

    def audio_callback(self, in_data, frame_count, time_info, status):
        if self.is_speaking or self.is_processing:
            if self.loop:
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self.emit_telemetry('telemetry_mic', {"energy": 0}))
                )
            return (None, pyaudio.paContinue)

        if self.loop:
            audio_array = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
            energy = int(np.sqrt(np.mean(np.square(audio_array))))
            
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.emit_telemetry('telemetry_mic', {"energy": energy}))
            )

            audio_float32 = audio_array / 32768.0
            tensor_chunk = torch.from_numpy(audio_float32)
            speech_prob = self.vad_model(tensor_chunk, SAMPLE_RATE).item()
            is_speech = speech_prob > self.vad_threshold

            if is_speech:
                if not self.recording:
                    self.recording = True
                    if self.interaction_mode == "wakeword":
                        self.loop.call_soon_threadsafe(self._cancel_wake_session_timeout)
                    self.audio_buffer.extend(self.pre_padding)
                    self.pre_padding = []
                    self.speech_samples = 0
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self.emit_telemetry('telemetry_vad', {"is_speaking": True}))
                    )
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self._set_engine_state("listening"))
                    )
                self.audio_buffer.extend(audio_float32)
                self.speech_samples += len(audio_float32)
                self.silence_samples = 0
            else:
                if self.recording:
                    self.audio_buffer.extend(audio_float32)
                    self.silence_samples += len(audio_float32)

                    # Una sola ventana silenciosa (~32 ms) no debe cerrar una frase.
                    if self.silence_samples >= SAMPLE_RATE * VAD_END_SILENCE_SECONDS:
                        self.recording = False
                        self.loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(self.emit_telemetry('telemetry_vad', {"is_speaking": False}))
                        )

                        if self.speech_samples >= SAMPLE_RATE * STT_MIN_SPEECH_SECONDS:
                            audio_to_process = np.array(self.audio_buffer, dtype=np.float32)
                            # Marcamos antes de programar la corrutina para no aceptar un
                            # segundo fragmento mientras Whisper procesa el primero.
                            self.is_processing = True
                            self.loop.call_soon_threadsafe(
                                lambda: asyncio.create_task(self.process_speech(audio_to_process))
                            )
                        else:
                            print("[Engine] Audio descartado: voz demasiado corta para STT.")
                        self.audio_buffer = []
                        self.silence_samples = 0
                        self.speech_samples = 0
                else:
                    self.pre_padding.extend(audio_float32)
                    if len(self.pre_padding) > SAMPLE_RATE * VAD_PRE_PADDING_SECONDS:
                        self.pre_padding = self.pre_padding[-int(SAMPLE_RATE * VAD_PRE_PADDING_SECONDS):]

        return (in_data, pyaudio.paContinue)

    async def process_speech(self, audio_data: np.ndarray):
        self.is_processing = True
        await self._set_engine_state("processing")
        try:
            if self.stt_provider == "elevenlabs" and self.elevenlabs_stt:
                print("[Engine] Transcribiendo con ElevenLabs STT (Scribe Cloud)...", flush=True)
                # Convertir float32 array (-1.0 to 1.0) a int16 pcm bytes
                pcm_int16 = (audio_data * 32767).astype(np.int16).tobytes()
                text = await self.elevenlabs_stt.transcribe_audio_bytes(
                    pcm_int16,
                    sample_rate=SAMPLE_RATE,
                    language_code="spa"
                )
            else:
                print("[Engine] Transcribiendo con Whisper (GPU ultra-fast)...", flush=True)
                padding = np.zeros(int(SAMPLE_RATE * 0.2), dtype=np.float32)
                audio_padded = np.concatenate([audio_data, padding])

                segments, _ = self.stt_model.transcribe(
                    audio_padded,
                    beam_size=STT_BEAM_SIZE,
                    language="es",
                    initial_prompt=self.stt_prompt or None,
                    vad_filter=STT_VAD_FILTER,
                    condition_on_previous_text=STT_CONDITION_ON_PREVIOUS_TEXT,
                )
                text = " ".join([segment.text for segment in segments]).strip()

            if not text or len(text) < 2:
                return
                
            # Filtro anti-alucinaciones: Whisper a veces escupe el initial_prompt cuando hay ruido
            if text.lower().replace(",", "") == STT_INITIAL_PROMPT.lower().replace(",", ""):
                print(f"[Engine] Alucinación de Whisper filtrada: {text}", flush=True)
                return

            print(f"[STT Transcrito]: '{text}'", flush=True)

            if self.interaction_mode == "wakeword":
                if self.awaiting_user_query:
                    self.awaiting_user_query = False
                elif self.wake_session_active:
                    # La sesión sigue abierta: aceptamos turnos posteriores sin repetir wake word.
                    pass
                elif not self._contains_wake_word(text):
                    print(f"[Engine] Wakeword '{self.wake_word}' no detectada en: '{text}'", flush=True)
                    return
                else:
                    self.wake_session_active = True
                    text = self._remove_wake_word(text)
                    if not text:
                        self.awaiting_user_query = True
                        self._schedule_wake_session_timeout()
                        print(f"[Engine] Wake word detectada. Esperando consulta: {self.wake_word}.", flush=True)
                        asyncio.create_task(self._set_engine_state("idle"))
                        return

            print(f"[Usuario]: {text}")
            await self.emit_telemetry('telemetry_stt', {"text": text})
            await self.emit_telemetry('telemetry_llm_clear', {})
            await self.ask_llm(text)
        finally:
            self.is_processing = False

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFD", text.lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    def _contains_wake_word(self, text: str) -> bool:
        norm_text = self._normalize_text(text)
        norm_wake = self._normalize_text(self.wake_word).replace(" ", "")
        
        if norm_wake == "kodavox":
            # Coincide con kodavox, koda vox, codavox, coda vox, kodabox, koda box, codabox, coda box, koda, coda
            pattern = r"\b(koda|coda)\s*(vox|box)?\b"
            return bool(re.search(pattern, norm_text, flags=re.IGNORECASE))
            
        return bool(re.search(re.escape(self.wake_word), text, flags=re.IGNORECASE))

    def _remove_wake_word(self, text: str) -> str:
        norm_wake = self._normalize_text(self.wake_word).replace(" ", "")
        if norm_wake == "kodavox":
            # Usar regex normalizado para remover del texto original
            match = re.search(r"\b(koda|coda)\s*(vox|box)?\b", text, flags=re.IGNORECASE)
        else:
            match = re.search(re.escape(self.wake_word), text, flags=re.IGNORECASE)
            
        if match:
            return text[match.end():].lstrip(" ,.:;!?")
        return ""

    def _cancel_wake_session_timeout(self) -> None:
        if self.wake_session_timeout_task and not self.wake_session_timeout_task.done():
            self.wake_session_timeout_task.cancel()
        self.wake_session_timeout_task = None

    def _schedule_wake_session_timeout(self) -> None:
        if self.interaction_mode != "wakeword":
            return

        self._cancel_wake_session_timeout()
        self.wake_session_token += 1
        token = self.wake_session_token
        self.wake_session_timeout_task = asyncio.create_task(
            self._expire_wake_session(token)
        )

    async def _expire_wake_session(self, token: int) -> None:
        try:
            await asyncio.sleep(self.wake_session_timeout)
        except asyncio.CancelledError:
            return

        if token != self.wake_session_token or self.is_speaking or self.is_processing or self.recording:
            return

        self.wake_session_active = False
        self.awaiting_user_query = False
        self.wake_session_timeout_task = None
        self.conversation_history.clear()
        print(f"[Engine] Sesión expirada; vuelve a decir {self.wake_word} para continuar.")
        await self._set_engine_state("idle")

    async def ask_llm(self, text: str):
        self.is_speaking = True 
        
        # 1. Inyección de Contexto RAG
        prompt = text
        if self.active_rag_collection:
            try:
                if self.rag_service is None:
                    from services.rag_chroma import ChromaRAGService
                    self.rag_service = ChromaRAGService()
                context = await asyncio.to_thread(self.rag_service.get_relevant_context, self.active_rag_collection, text)
                if context:
                    print(f"[Engine] Contexto RAG recuperado de '{self.active_rag_collection}'")
                    prompt = f"Utiliza la siguiente información de la Base de Conocimientos para responder a la pregunta del usuario. Si la información no responde la pregunta, usa tu propio conocimiento pero dale prioridad al contexto dado.\n\nContexto:\n{context}\n\nPregunta del Usuario:\n{text}"
            except Exception as e:
                print(f"[Engine RAG Error] {e}")

        self.conversation_history.append({"role": "user", "content": prompt})
        
        # 2. Verificación de Redis Cache para preguntas/respuestas frecuentes
        try:
            from services.redis_cache import redis_cache
            cached_data = redis_cache.get(text)
            if cached_data:
                cached_text = cached_data.get("text", "")
                await self.emit_telemetry('telemetry_llm', {"token": cached_text, "provider": "Redis Cache"})
                self.conversation_history.append({"role": "assistant", "content": cached_text})
                await self.play_tts(cached_text)
                await asyncio.sleep(0.5)
                self.is_speaking = False
                if self.wake_session_active:
                    self._schedule_wake_session_timeout()
                return
        except Exception as cache_err:
            print(f"[Redis Cache Error] {cache_err}")

        full_response_buffer = []

        print(f"[Engine] Pensando con {self.llm_provider.provider_name} ({self.llm_provider.model_name})...")
        
        if TTS_PROVIDER == "elevenlabs":
            sentence_buffer = ""
            try:
                async for token in self.llm_provider.generate_stream(prompt, system_prompt=self.personality_prompt, history=self.conversation_history[:-1]):
                    if token:
                        await self.emit_telemetry('telemetry_llm', {"token": token, "provider": self.llm_provider.provider_name})
                        sentence_buffer += token
                        full_response_buffer.append(token)
                        if any(char in token for char in ['.', '!', '?', '\n']):
                            cleaned_sentence = sentence_buffer.strip()
                            if cleaned_sentence:
                                await self.play_elevenlabs_tts(cleaned_sentence)
                            sentence_buffer = ""
            except Exception as error:
                print(f"[Engine LLM Error] {error}", flush=True)
                
            if sentence_buffer.strip():
                await self.play_elevenlabs_tts(sentence_buffer.strip())
        else:
            sentence_buffer = ""
            try:
                async for token in self.llm_provider.generate_stream(prompt, system_prompt=self.personality_prompt, history=self.conversation_history[:-1]):
                    if token:
                        await self.emit_telemetry('telemetry_llm', {"token": token, "provider": self.llm_provider.provider_name})
                        sentence_buffer += token
                        full_response_buffer.append(token)
                        if any(char in token for char in ['.', '!', '?', '\n']):
                            await self.play_tts(sentence_buffer.strip())
                            sentence_buffer = ""
            except Exception as error:
                print(f"[Engine LLM Error] {error}")
                
            if sentence_buffer.strip():
                await self.play_tts(sentence_buffer.strip())

        final_assistant_text = "".join(full_response_buffer)
        self.conversation_history.append({"role": "assistant", "content": final_assistant_text})

        # Guardar en Redis Cache para consultas futuras si no fue RAG dinámico
        if final_assistant_text.strip() and not self.active_rag_collection:
            try:
                from services.redis_cache import redis_cache
                redis_cache.set(text, final_assistant_text)
            except Exception as cache_err:
                print(f"[Redis Cache Store Error] {cache_err}")

        # Esperamos medio segundo extra antes de "encender" el micrófono
        # para que cualquier eco en la habitación termine de disiparse.
        await asyncio.sleep(0.5)
        self.is_speaking = False
        
        # Reiniciar el contador de 10 segundos justo ahora que terminó de hablar.
        if self.wake_session_active:
            self._schedule_wake_session_timeout()

    async def ask_ollama(self, text: str):
        """Método de compatibilidad hacia atrás."""
        await self.ask_llm(text)

    async def play_tts(self, text: str):
        if not text: return
        if TTS_PROVIDER == "off":
            return

        if TTS_PROVIDER == "piper":
            await self.play_piper_tts(text)
            return

        if TTS_PROVIDER == "elevenlabs":
            await self.play_elevenlabs_tts(text)
            return

        print(f"[TTS] Sintetizando (XTTS): {text}")
        await self.emit_telemetry('telemetry_tts', {"is_playing": True})
        
        try:
            async with httpx.AsyncClient() as client:
                payload = {"text": text}
                async with client.stream("POST", TTS_URL, json=payload, timeout=30.0) as response:
                    response.raise_for_status()
                    stream = self.pa.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=24000,
                        frames_per_buffer=1024
                    ) if self.native_audio_output else None
                    # Acumular bytes para evitar microcortes y subdesbordamiento de buffer (underflow)
                    audio_buffer = b""
                    min_chunk_size = 4096  # ~85ms de audio a 24kHz 16-bit mono

                    async for chunk in response.aiter_bytes():
                        audio_buffer += chunk
                        while len(audio_buffer) >= min_chunk_size:
                            to_write = audio_buffer[:min_chunk_size]
                            audio_buffer = audio_buffer[min_chunk_size:]
                            import base64
                            await self.emit_telemetry('telemetry_audio_stream', {"audio": base64.b64encode(to_write).decode('utf-8')})
                            if stream:
                                await asyncio.to_thread(stream.write, to_write)
                            
                    # Escribir el remanente en el buffer
                    if audio_buffer:
                        import base64
                        await self.emit_telemetry('telemetry_audio_stream', {"audio": base64.b64encode(audio_buffer).decode('utf-8')})
                        if stream:
                            await asyncio.to_thread(stream.write, audio_buffer)

                    if stream:
                        stream.stop_stream()
                        stream.close()
        except Exception as e:
            print(f"[TTS Error] {e}")
            
        await self.emit_telemetry('telemetry_tts', {"is_playing": False})

    async def play_piper_tts(self, text: str):
        """Sintetiza con Piper fuera del event loop y reproduce PCM localmente."""
        if self.piper_tts is None:
            try:
                from services.piper_tts import PiperTTSService
                self.piper_tts = PiperTTSService(
                    model_path=PIPER_MODEL_PATH,
                    length_scale=PIPER_LENGTH_SCALE,
                    noise_scale=PIPER_NOISE_SCALE,
                    speaker_id=PIPER_SPEAKER_ID
                )
            except Exception as e:
                print(f"[Piper Error] Error al cargar PiperTTSService: {e}")
                return

        print(f"[TTS] Sintetizando (Piper): {text}")
        await self.emit_telemetry('telemetry_tts', {"is_playing": True})
        try:
            sample_rate, audio = await asyncio.to_thread(self.piper_tts.synthesize, text)
            if not audio:
                return

            stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                output=True,
                frames_per_buffer=1024,
            ) if self.native_audio_output else None
            try:
                import base64
                
                # Split in smaller chunks for socketio streaming if needed, or send all
                chunk_size = 4096
                for i in range(0, len(audio), chunk_size):
                    chunk = audio[i:i+chunk_size]
                    await self.emit_telemetry('telemetry_audio_stream', {"audio": base64.b64encode(chunk).decode('utf-8')})
                    if stream:
                        await asyncio.to_thread(stream.write, chunk)
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
        except Exception as error:
            print(f"[Piper Error] {error}")
        finally:
            await self.emit_telemetry('telemetry_tts', {"is_playing": False})

    async def play_elevenlabs_tts(self, text: str):
        """Sintetiza con ElevenLabs API y reproduce el audio PCM en tiempo real."""
        if self.elevenlabs_tts is None or self.elevenlabs_tts.voice_id != self.active_voice_id:
            from services.elevenlabs_tts import ElevenLabsTTSService
            self.elevenlabs_tts = ElevenLabsTTSService(voice_id=self.active_voice_id)
            self._update_elevenlabs_settings()

        print(f"[TTS] Sintetizando (ElevenLabs): {text}")
        await self.emit_telemetry('telemetry_tts', {"is_playing": True})
        try:
            stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=1024,
            ) if self.native_audio_output else None
            try:
                async for chunk in self.elevenlabs_tts.stream_audio_pcm(text):
                    if chunk:
                        import base64
                        await self.emit_telemetry('telemetry_audio_stream', {"audio": base64.b64encode(chunk).decode('utf-8')})
                        if stream:
                            await asyncio.to_thread(stream.write, chunk)
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
        except Exception as error:
            print(f"[ElevenLabs Error] {error}")
        finally:
            await self.emit_telemetry('telemetry_tts', {"is_playing": False})

    async def play_elevenlabs_tts_stream(self, text_iterator):
        """Sintetiza con ElevenLabs WS y reproduce el audio PCM en tiempo real."""
        if self.elevenlabs_tts is None or self.elevenlabs_tts.voice_id != self.active_voice_id:
            self.elevenlabs_tts = ElevenLabsTTSService(voice_id=self.active_voice_id)
            self._update_elevenlabs_settings()

        print("[TTS] Iniciando Input Streaming (ElevenLabs)...")
        await self.emit_telemetry('telemetry_tts', {"is_playing": True})
        try:
            stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=1024,
            ) if self.native_audio_output else None
            try:
                async for chunk in self.elevenlabs_tts.stream_input_pcm(text_iterator):
                    if chunk:
                        import base64
                        await self.emit_telemetry('telemetry_audio_stream', {"audio": base64.b64encode(chunk).decode('utf-8')})
                        if stream:
                            await asyncio.to_thread(stream.write, chunk)
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
        except Exception as error:
            print(f"[ElevenLabs Stream Error] {error}")
        finally:
            await self.emit_telemetry('telemetry_tts', {"is_playing": False})

    def run(self):
        self.stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE, stream_callback=self.audio_callback)
        print("[Engine] Micrófono Abierto.")
        self.stream.start_stream()

engine = MonolithicEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.loop = asyncio.get_running_loop()
    await engine.setup_tts()
    engine.run()
    yield
    if hasattr(engine, 'stream'):
        engine.stream.stop_stream()
        engine.stream.close()
    engine.pa.terminate()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rutas de Gestión de RAG (ChromaDB) ---

@app.get("/api/rag/collections")
async def get_collections():
    collections = engine.rag_service.list_collections()
    return {"collections": collections, "active": engine.active_rag_collection}

@app.post("/api/rag/collections")
async def create_collection(name: str = Body(..., embed=True)):
    engine.rag_service.create_collection(name)
    return {"message": f"Colección '{name}' creada o ya existente."}

@app.delete("/api/rag/collections/{name}")
async def delete_collection(name: str):
    engine.rag_service.delete_collection(name)
    if engine.active_rag_collection == name:
        engine.active_rag_collection = ""
        engine._save_engine_state()
    return {"message": f"Colección '{name}' eliminada."}

@app.post("/api/rag/active")
async def set_active_collection(name: str = Body(..., embed=True)):
    engine.active_rag_collection = name if name.lower() != "none" else ""
    engine._save_engine_state()
    return {"message": f"Colección activa cambiada a '{engine.active_rag_collection}'"}

@app.post("/api/rag/upload")
async def upload_document(collection: str = Form(...), file: UploadFile = File(...)):
    try:
        content = await file.read()
        engine.rag_service.add_document(collection, file.filename, content)
        return {"message": f"Archivo '{file.filename}' indexado correctamente en '{collection}'."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Rutas de Gestión de Configuración (Personalidad y Voces) ---

@app.get("/api/config/personality")
async def get_personality():
    return {"personality_prompt": engine.personality_prompt}

@app.post("/api/config/personality")
async def set_personality(prompt: str = Body(..., embed=True)):
    engine.personality_prompt = prompt
    engine._save_engine_state()
    return {"message": "Personalidad actualizada"}

@app.post("/api/config/voices/clone")
async def clone_voice(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de ElevenLabs no configurada")
        
    url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {
        "xi-api-key": api_key,
        "Accept": "application/json"
    }
    
    file_content = await file.read()
    
    files = [
        ("files", (file.filename, file_content, file.content_type))
    ]
    data = {
        "name": name,
        "description": "Clonado desde KodaVox Dashboard"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data, files=files, timeout=60.0)
            if response.status_code != 200:
                print(f"[ElevenLabs Error] {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Error al clonar en ElevenLabs")
                
            result = response.json()
            new_voice_id = result.get("voice_id")
            
            if new_voice_id:
                engine.elevenlabs_voices.append({"name": name, "id": new_voice_id})
                engine._save_engine_state()
                return {"message": f"Voz '{name}' clonada exitosamente", "voice_id": new_voice_id}
            else:
                raise HTTPException(status_code=500, detail="No se recibió un ID de voz")
                
    except Exception as e:
        print(f"[ElevenLabs Exception] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config/voices")
async def get_voices():
    return {
        "voices": engine.elevenlabs_voices,
        "active_voice_id": engine.active_voice_id,
        "settings": {
            "stability": getattr(engine, 'voice_stability', 0.5),
            "similarity_boost": getattr(engine, 'voice_similarity_boost', 0.75),
            "style": getattr(engine, 'voice_style', 0.0),
            "use_speaker_boost": getattr(engine, 'voice_use_speaker_boost', True)
        }
    }

@app.post("/api/config/voices")
async def add_voice(name: str = Body(...), id: str = Body(...)):
    if any(v["id"] == id for v in engine.elevenlabs_voices):
        raise HTTPException(status_code=400, detail="La voz con este ID ya existe")
    engine.elevenlabs_voices.append({"name": name, "id": id})
    engine._save_engine_state()
    return {"message": f"Voz '{name}' agregada"}

@app.delete("/api/config/voices/{voice_id}")
async def delete_voice(voice_id: str):
    engine.elevenlabs_voices = [v for v in engine.elevenlabs_voices if v["id"] != voice_id]
    engine._save_engine_state()
    return {"message": "Voz eliminada"}

@app.post("/api/config/voices/active")
async def set_active_voice(payload: dict = Body(...)):
    voice_id = payload.get("id")
    if not any(v["id"] == voice_id for v in engine.elevenlabs_voices):
        raise HTTPException(status_code=400, detail="Voice ID no registrado")
        
    engine.active_voice_id = voice_id
    if getattr(engine, 'elevenlabs_tts', None) is not None:
        engine.elevenlabs_tts = ElevenLabsTTSService(voice_id=voice_id)
        engine._update_elevenlabs_settings()
        
    engine._save_engine_state()
    return {"message": "Voz activa actualizada"}

@app.post("/api/config/voices/settings")
async def update_voice_settings(payload: dict = Body(...)):
    engine.voice_stability = float(payload.get("stability", getattr(engine, 'voice_stability', 0.5)))
    engine.voice_similarity_boost = float(payload.get("similarity_boost", getattr(engine, 'voice_similarity_boost', 0.75)))
    engine.voice_style = float(payload.get("style", getattr(engine, 'voice_style', 0.0)))
    engine.voice_use_speaker_boost = bool(payload.get("use_speaker_boost", getattr(engine, 'voice_use_speaker_boost', True)))
    
    engine._update_elevenlabs_settings()
    engine._save_engine_state()
    return {"message": "Voice settings updated successfully"}

@app.get("/api/config/wakeword")
async def get_wakeword():
    return {
        "wake_word": engine.wake_word,
        "wake_session_timeout": engine.wake_session_timeout
    }

@app.post("/api/config/wakeword")
async def set_wakeword(word: str = Body(None, embed=True), timeout: int = Body(None, embed=True)):
    if word is not None:
        engine.wake_word = word
    if timeout is not None:
        engine.wake_session_timeout = int(timeout)
    engine._save_engine_state()
    return {"message": "Configuración de Wakeword actualizada exitosamente"}

@app.get("/api/config/hardware")
async def get_hardware():
    return {
        "native_audio_output": getattr(engine, 'native_audio_output', True),
        "robot_face_sync": getattr(engine, 'robot_face_sync', False)
    }

@app.post("/api/config/hardware")
async def set_hardware(payload: dict = Body(...)):
    if "native_audio_output" in payload:
        engine.native_audio_output = payload["native_audio_output"]
    if "robot_face_sync" in payload:
        engine.robot_face_sync = payload["robot_face_sync"]
        
    engine._save_engine_state()
    return {"message": "Configuración de hardware actualizada exitosamente"}

@app.post("/api/tts/test")
async def test_tts(payload: dict = Body(...)):
    text = payload.get("text", "Hola, esta es una prueba de voz de KodaVox.")
    if TTS_PROVIDER == "off":
        raise HTTPException(status_code=400, detail="El proveedor TTS está desactivado (off).")
    
    # Lo lanzamos como tarea en segundo plano para no bloquear la petición HTTP
    asyncio.create_task(engine.play_tts(text))
    return {"message": "Sintetizando voz..."}

@app.get("/api/diagnostics/health")
async def get_health():
    return {
        "vad": engine.vad_model is not None,
        "stt": engine.stt_model is not None or engine.elevenlabs_stt is not None,
        "stt_provider": engine.stt_provider,
        "llm": engine.llm_provider is not None,
        "rag": engine.rag_service is not None,
        "microphone_active": engine.stream is not None and engine.stream.is_active(),
        "is_speaking": engine.is_speaking,
        "is_processing": engine.is_processing
    }

@app.get("/api/diagnostics/usage")
async def get_usage():
    return tracker.get_all_stats()

@app.get("/api/diagnostics/providers")
async def get_providers_status():
    status = {
        "elevenlabs": {"status": "unknown", "details": None},
        "openai": {"status": "unknown"},
        "gemini": {"status": "unknown"}
    }
    
    # ElevenLabs Subscription
    el_key = os.getenv("ELEVENLABS_API_KEY")
    if el_key:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://api.elevenlabs.io/v1/user/subscription",
                    headers={"xi-api-key": el_key},
                    timeout=5.0
                )
                if res.status_code == 200:
                    data = res.json()
                    status["elevenlabs"] = {
                        "status": "ok",
                        "character_count": data.get("character_count"),
                        "character_limit": data.get("character_limit"),
                        "status_tier": data.get("status")
                    }
                else:
                    status["elevenlabs"] = {"status": "error", "code": res.status_code}
        except Exception as e:
            status["elevenlabs"] = {"status": "error", "message": str(e)}
    else:
        status["elevenlabs"] = {"status": "missing_key"}

    # OpenAI Ping
    oa_key = os.getenv("OPENAI_API_KEY")
    if oa_key:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {oa_key}"},
                    timeout=5.0
                )
                status["openai"] = {"status": "ok" if res.status_code == 200 else f"error_{res.status_code}"}
        except Exception as e:
            status["openai"] = {"status": "error", "message": str(e)}
    else:
        status["openai"] = {"status": "missing_key"}

    # Gemini Ping
    gem_key = os.getenv("GEMINI_API_KEY")
    if gem_key:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={gem_key}",
                    timeout=5.0
                )
                status["gemini"] = {"status": "ok" if res.status_code == 200 else f"error_{res.status_code}"}
        except Exception as e:
            status["gemini"] = {"status": "error", "message": str(e)}
    else:
        status["gemini"] = {"status": "missing_key"}
        
    return status

@app.post("/api/config/export")
async def export_config(payload: dict = Body(...)):
    include_env = payload.get("include_env", False)
    include_rag = payload.get("include_rag", False)
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    state_path = os.path.join(os.path.dirname(__file__), "data", "engine_state.json")
    env_path = os.path.join(project_root, ".env")
    chroma_path = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
    
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "kodavox_full_profile.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        manifest = {
            "has_state": True,
            "has_env": include_env,
            "has_rag": include_rag,
            "version": "2.0"
        }
        zipf.writestr("manifest.json", json.dumps(manifest))
        
        if os.path.exists(state_path):
            zipf.write(state_path, "engine_state.json")
            
        if include_env and os.path.exists(env_path):
            zipf.write(env_path, ".env")
            
        if include_rag and os.path.exists(chroma_path):
            for root, _, files in os.walk(chroma_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.join("chroma_db", os.path.relpath(file_path, chroma_path))
                    zipf.write(file_path, arcname)
                    
    return FileResponse(path=zip_path, filename="kodavox_full_profile.zip", media_type="application/zip")

async def restart_server_task():
    await asyncio.sleep(2)
    os.execv(sys.executable, ['python'] + sys.argv)

@app.post("/api/config/import")
async def import_config(file: UploadFile = File(...)):
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un ZIP (.zip)")
        
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "uploaded.zip")
    
    try:
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_dir)
            
        manifest_path = os.path.join(extract_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            raise HTTPException(status_code=400, detail="El archivo no es un perfil de KodaVox válido (falta manifest.json)")
            
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        needs_restart = False
        
        if manifest.get("has_state"):
            state_src = os.path.join(extract_dir, "engine_state.json")
            state_dest = os.path.join(os.path.dirname(__file__), "data", "engine_state.json")
            if os.path.exists(state_src):
                shutil.copy2(state_src, state_dest)
                engine._load_engine_state()
                if TTS_PROVIDER == "elevenlabs" and getattr(engine, 'active_voice_id', None):
                    engine.elevenlabs_tts = ElevenLabsTTSService(voice_id=engine.active_voice_id)
                    engine._update_elevenlabs_settings()
                    
        if manifest.get("has_env"):
            env_src = os.path.join(extract_dir, ".env")
            env_dest = os.path.join(project_root, ".env")
            if os.path.exists(env_src):
                shutil.copy2(env_src, env_dest)
                needs_restart = True
                
        if manifest.get("has_rag"):
            chroma_src = os.path.join(extract_dir, "chroma_db")
            chroma_dest = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
            if os.path.exists(chroma_src):
                if os.path.exists(chroma_dest):
                    shutil.rmtree(chroma_dest)
                shutil.copytree(chroma_src, chroma_dest)
                needs_restart = True
                
        if needs_restart:
            asyncio.create_task(restart_server_task())
            
        return {"message": "Perfil importado exitosamente", "needs_restart": needs_restart}
    except Exception as e:
        print(f"[Import Error] {e}")
        raise HTTPException(status_code=500, detail=f"Error al importar configuración: {e}")

socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    engine_port = int(os.getenv("ENGINE_PORT", "5000"))
    uvicorn.run(socket_app, host="0.0.0.0", port=engine_port, log_level="warning")
