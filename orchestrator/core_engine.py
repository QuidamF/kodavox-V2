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
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from faster_whisper import WhisperModel
from contextlib import asynccontextmanager
from services.piper_tts import PiperTTSService
from services.llm_provider import LLMFactory, DEFAULT_SYSTEM_PROMPT
from services.elevenlabs_tts import ElevenLabsTTSService
from services.rag_chroma import ChromaRAGService

# --- Configuración Base ---
SAMPLE_RATE = 16000
CHUNK_SIZE = 512
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
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
        
        # 3. STT (Whisper) - Regresamos a GPU pero con CUANTIZACIÓN AGRESIVA (int8_float16)
        # Esto reduce el consumo de VRAM a menos de la mitad que float16, manteniendo la velocidad.
        print(f"[Engine] Cargando modelo Whisper {STT_MODEL} en GPU (Modo ultra-eficiente int8_float16)...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # int8_float16 es el truco para GPUs con poca memoria pero que necesitan velocidad
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
        self.awaiting_user_query = False
        self.wake_session_active = False
        self.wake_session_token = 0
        self.wake_session_timeout_task = None
        self.loop = None
        self.vad_threshold = VAD_THRESHOLD
        self.interaction_mode = INTERACTION_MODE
        if self.interaction_mode not in ["active", "wakeword"]:
            print(f"[Engine] INTERACTION_MODE inválido: {INTERACTION_MODE}. Usando active.")
        print(f"[Engine] Modo de interacción: {self.interaction_mode}. Umbral VAD: {self.vad_threshold}.")
        self.piper_tts = None
        self.elevenlabs_tts = None
        
        # RAG Local Inicialización
        self.rag_service = ChromaRAGService()
        self.active_rag_collection = ""
        self._load_engine_state()
        if self.active_rag_collection:
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
                    self.wake_word = state.get("wake_word", os.getenv("WAKE_WORD", "KodaVox"))
            else:
                self.active_rag_collection = os.getenv("RAG_ACTIVE_COLLECTION", "")
                self.personality_prompt = DEFAULT_SYSTEM_PROMPT
                default_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
                self.elevenlabs_voices = [{"name": "Default (Env)", "id": default_voice_id}]
                self.active_voice_id = default_voice_id
                self.wake_word = os.getenv("WAKE_WORD", "KodaVox")
        except Exception as e:
            print(f"[Engine] Error cargando estado: {e}")
            self.active_rag_collection = os.getenv("RAG_ACTIVE_COLLECTION", "")
            self.personality_prompt = DEFAULT_SYSTEM_PROMPT
            default_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            self.elevenlabs_voices = [{"name": "Default (Env)", "id": default_voice_id}]
            self.active_voice_id = default_voice_id
            self.wake_word = os.getenv("WAKE_WORD", "KodaVox")

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
                    "wake_word": self.wake_word
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

    def audio_callback(self, in_data, frame_count, time_info, status):
        if not self.is_speaking and not self.is_processing and self.loop:
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
        try:
            print("[Engine] Transcribiendo (GPU ultra-fast)...")
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
                print(f"[Engine] Alucinación de Whisper filtrada: {text}")
                return

            if self.interaction_mode == "wakeword":
                if self.awaiting_user_query:
                    self.awaiting_user_query = False
                elif self.wake_session_active:
                    # La sesión sigue abierta: aceptamos turnos posteriores sin repetir wake word.
                    pass
                elif not self._contains_wake_word(text):
                    print(f"[Engine] Ignorado sin wake word: {text}")
                    return
                else:
                    self.wake_session_active = True
                    text = self._remove_wake_word(text)
                    if not text:
                        self.awaiting_user_query = True
                        self._schedule_wake_session_timeout()
                        print(f"[Engine] Wake word detectada. Esperando consulta: {self.wake_word}.")
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
        normalized_wake = self._normalize_text(self.wake_word).replace(" ", "")
        normalized_text = self._normalize_text(text).replace(" ", "")
        return normalized_wake in normalized_text

    def _remove_wake_word(self, text: str) -> str:
        # Whisper puede transcribir “KodaVox” como “Koda Vox”.
        if self._normalize_text(self.wake_word).replace(" ", "") == "kodavox":
            match = re.search(r"koda\s*vox", text, flags=re.IGNORECASE)
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
            await asyncio.sleep(WAKE_SESSION_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            return

        if token != self.wake_session_token or self.is_speaking or self.is_processing or self.recording:
            return

        self.wake_session_active = False
        self.awaiting_user_query = False
        self.wake_session_timeout_task = None
        print(f"[Engine] Sesión expirada; vuelve a decir {self.wake_word} para continuar.")

    async def ask_llm(self, text: str):
        self.is_speaking = True 
        
        # 1. Inyección de Contexto RAG
        prompt = text
        if self.active_rag_collection:
            try:
                context = await asyncio.to_thread(self.rag_service.get_relevant_context, self.active_rag_collection, text)
                if context:
                    print(f"[Engine] Contexto RAG recuperado de '{self.active_rag_collection}'")
                    prompt = f"Utiliza la siguiente información de la Base de Conocimientos para responder a la pregunta del usuario. Si la información no responde la pregunta, usa tu propio conocimiento pero dale prioridad al contexto dado.\n\nContexto:\n{context}\n\nPregunta del Usuario:\n{text}"
            except Exception as e:
                print(f"[Engine RAG Error] {e}")

        print(f"[Engine] Pensando con {self.llm_provider.provider_name} ({self.llm_provider.model_name})...")
        
        if TTS_PROVIDER == "elevenlabs":
            async def token_generator():
                try:
                    async for token in self.llm_provider.generate_stream(prompt, system_prompt=self.personality_prompt):
                        if token:
                            await self.emit_telemetry('telemetry_llm', {"token": token, "provider": self.llm_provider.provider_name})
                            yield token
                except Exception as error:
                    print(f"[Engine LLM Error] {error}")
            
            await self.play_elevenlabs_tts_stream(token_generator())
        else:
            sentence_buffer = ""
            try:
                async for token in self.llm_provider.generate_stream(prompt, system_prompt=self.personality_prompt):
                    if token:
                        await self.emit_telemetry('telemetry_llm', {"token": token, "provider": self.llm_provider.provider_name})
                        sentence_buffer += token
                        if any(char in token for char in ['.', '!', '?', '\n']):
                            await self.play_tts(sentence_buffer.strip())
                            sentence_buffer = ""
            except Exception as error:
                print(f"[Engine LLM Error] {error}")
                
            if sentence_buffer.strip():
                await self.play_tts(sentence_buffer.strip())

        self.is_speaking = False
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
                        output=True,
                        frames_per_buffer=1024
                    )
                    # Acumular bytes para evitar microcortes y subdesbordamiento de buffer (underflow)
                    audio_buffer = b""
                    min_chunk_size = 4096  # ~85ms de audio a 24kHz 16-bit mono

                    async for chunk in response.aiter_bytes():
                        audio_buffer += chunk
                        while len(audio_buffer) >= min_chunk_size:
                            to_write = audio_buffer[:min_chunk_size]
                            audio_buffer = audio_buffer[min_chunk_size:]
                            await asyncio.to_thread(stream.write, to_write)
                            
                    # Escribir el remanente en el buffer
                    if audio_buffer:
                        await asyncio.to_thread(stream.write, audio_buffer)

                    stream.stop_stream()
                    stream.close()
        except Exception as e:
            print(f"[TTS Error] {e}")
            
        await self.emit_telemetry('telemetry_tts', {"is_playing": False})

    async def play_piper_tts(self, text: str):
        """Sintetiza con Piper fuera del event loop y reproduce PCM localmente."""
        if self.piper_tts is None:
            print("[Piper Error] Piper no está disponible; revisa el modelo y la configuración.")
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
            )
            try:
                await asyncio.to_thread(stream.write, audio)
            finally:
                stream.stop_stream()
                stream.close()
        except Exception as error:
            print(f"[Piper Error] {error}")
        finally:
            await self.emit_telemetry('telemetry_tts', {"is_playing": False})

    async def play_elevenlabs_tts(self, text: str):
        """Sintetiza con ElevenLabs API y reproduce el audio PCM en tiempo real."""
        if self.elevenlabs_tts is None or self.elevenlabs_tts.voice_id != self.active_voice_id:
            self.elevenlabs_tts = ElevenLabsTTSService(voice_id=self.active_voice_id)

        print(f"[TTS] Sintetizando (ElevenLabs): {text}")
        await self.emit_telemetry('telemetry_tts', {"is_playing": True})
        try:
            stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=1024,
            )
            try:
                async for chunk in self.elevenlabs_tts.stream_audio_pcm(text):
                    if chunk:
                        await asyncio.to_thread(stream.write, chunk)
            finally:
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

        print("[TTS] Iniciando Input Streaming (ElevenLabs)...")
        await self.emit_telemetry('telemetry_tts', {"is_playing": True})
        try:
            stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=1024,
            )
            try:
                async for chunk in self.elevenlabs_tts.stream_input_pcm(text_iterator):
                    if chunk:
                        await asyncio.to_thread(stream.write, chunk)
            finally:
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

@app.get("/api/config/voices")
async def get_voices():
    return {
        "voices": engine.elevenlabs_voices,
        "active_voice_id": engine.active_voice_id
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
async def set_active_voice(voice_id: str = Body(..., embed=True)):
    if any(v["id"] == voice_id for v in engine.elevenlabs_voices):
        engine.active_voice_id = voice_id
        engine._save_engine_state()
        return {"message": "Voz activa actualizada"}
    raise HTTPException(status_code=404, detail="ID de voz no encontrado en la lista")

@app.get("/api/config/wakeword")
async def get_wakeword():
    return {"wake_word": engine.wake_word}

@app.post("/api/config/wakeword")
async def set_wakeword(word: str = Body(..., embed=True)):
    engine.wake_word = word
    engine._save_engine_state()
    return {"message": "Wakeword actualizado exitosamente"}

socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=5000, log_level="warning")
