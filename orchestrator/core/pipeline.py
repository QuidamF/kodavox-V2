import asyncio
import os
import torch
import numpy as np
import pyaudio
import json
import websockets
from services.llm_provider import LLMFactory, DEFAULT_SYSTEM_PROMPT
from services.usage_tracker import tracker
from core.config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    STT_PROVIDER,
    STT_MODEL,
    STT_BEAM_SIZE,
    STT_INITIAL_PROMPT,
    STT_VAD_FILTER,
    STT_CONDITION_ON_PREVIOUS_TEXT,
    INTERACTION_MODE,
    WAKE_WORD,
    VAD_THRESHOLD,
    VAD_END_SILENCE_SECONDS,
    STT_MIN_SPEECH_SECONDS,
    VAD_PRE_PADDING_SECONDS,
    WAKE_SESSION_TIMEOUT_SECONDS,
    TTS_URL,
    TTS_CONFIG_URL,
    TTS_HEALTH_URL,
    TTS_PROVIDER,
    PIPER_MODEL_PATH,
    PIPER_LENGTH_SCALE,
    PIPER_NOISE_SCALE,
    PIPER_SPEAKER_ID,
    CONFIGURE_TTS_VOICE_ON_START,
    VOICE_SAMPLE,
)

class EnginePipeline:
    def __init__(self, sio):
        print("[Pipeline] Inicializando Pipeline del Motor KodaVox V2...")
        self.sio = sio
        self.pa = pyaudio.PyAudio()
        
        # VAD (Silero) en CPU
        print("[Pipeline] Cargando modelo Silero VAD en CPU...")
        self.vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        self.vad_model.to("cpu")
        self.get_speech_timestamps = utils[0]
        
        # STT (Whisper o ElevenLabs)
        self.stt_provider = STT_PROVIDER
        self.stt_model = None
        self.elevenlabs_stt = None
        
        if self.stt_provider == "elevenlabs":
            from services.elevenlabs_stt import ElevenLabsSTTService
            print("[Pipeline] Usando ElevenLabs STT (Scribe cloud)...", flush=True)
            self.elevenlabs_stt = ElevenLabsSTTService()
        else:
            print(f"[Pipeline] Cargando modelo Whisper {STT_MODEL} en GPU (int8_float16)...", flush=True)
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
        self.piper_tts = None
        self.elevenlabs_tts = None
        self.stream = None
        
        # RAG Local (Lazy Loaded)
        self.rag_service = None
        self.active_rag_collection = ""
        self.engine_state = "idle"
        
        self._load_engine_state()
        if self.active_rag_collection:
            from services.rag_chroma import ChromaRAGService
            self.rag_service = ChromaRAGService()
            print(f"[Pipeline] RAG Activado con colección: {self.active_rag_collection}")
            
        self.llm_provider = LLMFactory.get_provider()
        print(f"[Pipeline] Proveedor LLM inicializado: {self.llm_provider.provider_name} ({self.llm_provider.model_name}).")

    def _load_engine_state(self):
        state_path = os.path.join(os.path.dirname(__file__), "..", "data", "engine_state.json")
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
                    self.vad_threshold = state.get("vad_threshold", float(VAD_THRESHOLD))
                    self.vad_end_silence_seconds = state.get("vad_end_silence_seconds", float(VAD_END_SILENCE_SECONDS))
                    self.stt_min_speech_seconds = state.get("stt_min_speech_seconds", float(STT_MIN_SPEECH_SECONDS))
                    self.vad_pre_padding_seconds = state.get("vad_pre_padding_seconds", float(VAD_PRE_PADDING_SECONDS))
                    self.piper_length_scale = state.get("piper_length_scale", float(PIPER_LENGTH_SCALE) if PIPER_LENGTH_SCALE else 0.85)
                    self.piper_noise_scale = state.get("piper_noise_scale", float(PIPER_NOISE_SCALE) if PIPER_NOISE_SCALE else 0.75)
                    self.llm_temperature = state.get("llm_temperature", 0.7)
                    self.rag_strict_mode = state.get("rag_strict_mode", False)
                    self.native_audio_output = state.get("native_audio_output", True)
                    self.robot_face_sync = state.get("robot_face_sync", False)
                    self.enabled = state.get("enabled", True)
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
                self.vad_threshold = float(VAD_THRESHOLD)
                self.vad_end_silence_seconds = float(VAD_END_SILENCE_SECONDS)
                self.stt_min_speech_seconds = float(STT_MIN_SPEECH_SECONDS)
                self.vad_pre_padding_seconds = float(VAD_PRE_PADDING_SECONDS)
                self.piper_length_scale = float(PIPER_LENGTH_SCALE) if PIPER_LENGTH_SCALE else 0.85
                self.piper_noise_scale = float(PIPER_NOISE_SCALE) if PIPER_NOISE_SCALE else 0.75
                self.llm_temperature = 0.7
                self.rag_strict_mode = False
                self.native_audio_output = True
                self.robot_face_sync = False
                self.enabled = True
        except Exception as e:
            print(f"[Pipeline] Error cargando estado: {e}")
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
            self.vad_threshold = float(VAD_THRESHOLD)
            self.vad_end_silence_seconds = float(VAD_END_SILENCE_SECONDS)
            self.stt_min_speech_seconds = float(STT_MIN_SPEECH_SECONDS)
            self.vad_pre_padding_seconds = float(VAD_PRE_PADDING_SECONDS)
            self.piper_length_scale = float(PIPER_LENGTH_SCALE) if PIPER_LENGTH_SCALE else 0.85
            self.piper_noise_scale = float(PIPER_NOISE_SCALE) if PIPER_NOISE_SCALE else 0.75
            self.llm_temperature = 0.7
            self.rag_strict_mode = False
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
        state_path = os.path.join(os.path.dirname(__file__), "..", "data", "engine_state.json")
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
                    "vad_threshold": getattr(self, 'vad_threshold', 0.6),
                    "vad_end_silence_seconds": getattr(self, 'vad_end_silence_seconds', 0.7),
                    "stt_min_speech_seconds": getattr(self, 'stt_min_speech_seconds', 0.3),
                    "vad_pre_padding_seconds": getattr(self, 'vad_pre_padding_seconds', 0.2),
                    "piper_length_scale": getattr(self, 'piper_length_scale', 0.85),
                    "piper_noise_scale": getattr(self, 'piper_noise_scale', 0.75),
                    "llm_temperature": getattr(self, 'llm_temperature', 0.7),
                    "rag_strict_mode": getattr(self, 'rag_strict_mode', False),
                    "native_audio_output": self.native_audio_output,
                    "robot_face_sync": getattr(self, 'robot_face_sync', False),
                    "enabled": getattr(self, 'enabled', True)
                }, f, indent=4)
        except Exception as e:
            print(f"[Pipeline] Error guardando estado: {e}")

    async def setup_tts(self):
        if TTS_PROVIDER == "off":
            print("[Pipeline] TTS desactivado.")
            return

        if TTS_PROVIDER == "piper":
            try:
                from services.piper_tts import PiperTTSService
                self.piper_tts = PiperTTSService(
                    PIPER_MODEL_PATH,
                    length_scale=PIPER_LENGTH_SCALE,
                    noise_scale=float(PIPER_NOISE_SCALE) if PIPER_NOISE_SCALE else None,
                    speaker_id=int(PIPER_SPEAKER_ID) if PIPER_SPEAKER_ID else None,
                )
                await asyncio.to_thread(self.piper_tts.load)
                print(f"[Pipeline] Piper listo: {PIPER_MODEL_PATH}.")
            except Exception as error:
                self.piper_tts = None
                print(f"[Pipeline] No se pudo cargar Piper: {error}")
            return

        if TTS_PROVIDER == "elevenlabs":
            try:
                from services.elevenlabs_tts import ElevenLabsTTSService
                self.elevenlabs_tts = ElevenLabsTTSService()
                self._update_elevenlabs_settings()
                print(f"[Pipeline] ElevenLabs listo (Voice ID: {self.elevenlabs_tts.voice_id}).")
            except Exception as error:
                self.elevenlabs_tts = None
                print(f"[Pipeline] No se pudo inicializar ElevenLabs: {error}")
            return

    async def emit_telemetry(self, event: str, data: dict):
        if self.sio:
            await self.sio.emit(event, data)

    async def _set_engine_state(self, new_state: str):
        self.engine_state = new_state
        await self.emit_telemetry('telemetry_state', {
            "state": self.engine_state,
            "session_active": self.wake_session_active,
            "enabled": getattr(self, 'enabled', True)
        })
        
        if getattr(self, 'robot_face_sync', False):
            mood_map = {
                "disabled": "Dormido",
                "idle": "Alerta" if self.wake_session_active else "Neutral",
                "listening": "Escuchando",
                "processing": "Pensando",
                "wakeword_detected": "Sorprendido",
                "speaking": "Feliz"
            }
            mood = mood_map.get(new_state, "Dormido" if not getattr(self, "enabled", True) else "Neutral")
            try:
                asyncio.create_task(self._send_robot_face_mood(mood))
            except Exception:
                pass

    async def _send_robot_face_mood(self, mood: str):
        try:
            async with websockets.connect("ws://localhost:8760", open_timeout=1) as ws:
                payload = json.dumps({"type": "mood", "mood": mood})
                await ws.send(payload)
        except Exception:
            pass

    def audio_callback(self, in_data, frame_count, time_info, status):
        if not getattr(self, 'enabled', True):
            if self.loop:
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self.emit_telemetry('telemetry_mic', {"energy": 0}))
                )
            return (in_data, pyaudio.paContinue)
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

                    if self.silence_samples >= SAMPLE_RATE * self.vad_end_silence_seconds:
                        self.recording = False
                        self.loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(self.emit_telemetry('telemetry_vad', {"is_speaking": False}))
                        )

                        if self.speech_samples >= SAMPLE_RATE * self.stt_min_speech_seconds:
                            audio_to_process = np.array(self.audio_buffer, dtype=np.float32)
                            self.is_processing = True
                            self.loop.call_soon_threadsafe(
                                lambda: asyncio.create_task(self.process_speech(audio_to_process))
                            )
                        else:
                            print("[Pipeline] Audio descartado: voz demasiado corta para STT.")
                            self.loop.call_soon_threadsafe(
                                lambda: asyncio.create_task(self._set_engine_state("idle"))
                            )
                        self.audio_buffer = []
                        self.silence_samples = 0
                        self.speech_samples = 0
                else:
                    self.pre_padding.extend(audio_float32)
                    if len(self.pre_padding) > SAMPLE_RATE * self.vad_pre_padding_seconds:
                        self.pre_padding = self.pre_padding[-int(SAMPLE_RATE * self.vad_pre_padding_seconds):]

        return (in_data, pyaudio.paContinue)

    async def process_speech(self, audio_data: np.ndarray):
        self.is_processing = True
        await self._set_engine_state("processing")
        try:
            if self.stt_provider == "elevenlabs" and self.elevenlabs_stt:
                print("[Pipeline] Transcribiendo con ElevenLabs STT (Scribe Cloud)...", flush=True)
                pcm_int16 = (audio_data * 32767).astype(np.int16).tobytes()
                text = await self.elevenlabs_stt.transcribe_audio_bytes(
                    pcm_int16,
                    sample_rate=SAMPLE_RATE,
                    language_code="spa"
                )
            else:
                print("[Pipeline] Transcribiendo con Whisper (GPU ultra-fast)...", flush=True)
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

            if text.lower().replace(",", "") == STT_INITIAL_PROMPT.lower().replace(",", ""):
                print(f"[Pipeline] Alucinación de Whisper filtrada: {text}", flush=True)
                return

            print(f"[STT Transcrito]: '{text}'", flush=True)

            if self.interaction_mode == "wakeword":
                if self.awaiting_user_query:
                    self.awaiting_user_query = False
                elif self.wake_session_active:
                    pass
                elif not self._contains_wake_word(text):
                    print(f"[Pipeline] Wakeword '{self.wake_word}' no detectada en: '{text}'", flush=True)
                    return
                else:
                    self.wake_session_active = True
                    await self._set_engine_state("wakeword_detected")
                    text = self._remove_wake_word(text)
                    if not text:
                        self.awaiting_user_query = True
                        self._schedule_wake_session_timeout()
                        print(f"[Pipeline] Wake word detectada. Esperando consulta: {self.wake_word}.", flush=True)
                        await asyncio.sleep(0.4)
                        return

            print(f"[Usuario]: {text}")
            await self.emit_telemetry('telemetry_stt', {"text": text})
            await self.emit_telemetry('telemetry_llm_clear', {})
            await self.ask_llm(text)
        finally:
            self.is_processing = False
            if not self.is_speaking:
                await self._set_engine_state("idle")

    def _contains_wake_word(self, text: str) -> bool:
        from services.wake_word import wake_word_matcher
        detected, _ = wake_word_matcher.check_and_extract(text, self.wake_word)
        return detected

    def _remove_wake_word(self, text: str) -> str:
        from services.wake_word import wake_word_matcher
        _, clean_text = wake_word_matcher.check_and_extract(text, self.wake_word)
        return clean_text

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
        print(f"[Pipeline] Sesión expirada; vuelve a decir {self.wake_word} para continuar.")
        await self._set_engine_state("idle")

    async def ask_llm(self, text: str):
        self.is_speaking = True
        await self._set_engine_state("speaking")
        try:
            # 1. Verificación de Redis Cache
            try:
                from services.redis_cache import redis_cache
                cached_data = redis_cache.get(text)
                if cached_data:
                    cached_text = cached_data.get("text", "")
                    await self.emit_telemetry('telemetry_llm', {"token": cached_text, "provider": "Redis Cache"})
                    self.conversation_history.append({"role": "user", "content": text})
                    self.conversation_history.append({"role": "assistant", "content": cached_text})
                    await self.play_tts(cached_text)
                    await asyncio.sleep(0.5)
                    return
            except Exception as cache_err:
                print(f"[Redis Cache Error] {cache_err}")

            # 2. Contexto RAG
            prompt = text
            if self.active_rag_collection:
                try:
                    if self.rag_service is None:
                        from services.rag_chroma import ChromaRAGService
                        self.rag_service = ChromaRAGService()
                    context = await asyncio.to_thread(self.rag_service.get_relevant_context, self.active_rag_collection, text)
                    if context:
                        print(f"[Pipeline] Contexto RAG recuperado de '{self.active_rag_collection}' (Modo Estricto: {getattr(self, 'rag_strict_mode', False)})")
                        if getattr(self, 'rag_strict_mode', False):
                            prompt = f"RESPONDE ÚNICAMENTE usando la siguiente información de la Base de Conocimientos. Si la respuesta no está contenida en el contexto, indica amablemente que no posees esa información en tus datos cargados. NO inventes ni uses tu conocimiento general.\n\nContexto:\n{context}\n\nPregunta del Usuario:\n{text}"
                        else:
                            prompt = f"Utiliza la siguiente información de la Base de Conocimientos para responder a la pregunta del usuario. Si la información no responde la pregunta completa, usa tu propio conocimiento pero dale prioridad al contexto dado.\n\nContexto:\n{context}\n\nPregunta del Usuario:\n{text}"
                except Exception as e:
                    print(f"[Pipeline RAG Error] {e}")

            self.conversation_history.append({"role": "user", "content": prompt})
            full_response_buffer = []

            print(f"[Pipeline] Pensando con {self.llm_provider.provider_name} ({self.llm_provider.model_name}) [Temp: {getattr(self, 'llm_temperature', 0.7)}]...")
            
            temp = getattr(self, 'llm_temperature', 0.7)
            if TTS_PROVIDER == "elevenlabs":
                sentence_buffer = ""
                try:
                    async for token in self.llm_provider.generate_stream(prompt, system_prompt=self.personality_prompt, history=self.conversation_history[:-1], temperature=temp):
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
                    print(f"[Pipeline LLM Error] {error}", flush=True)
                    
                if sentence_buffer.strip():
                    await self.play_elevenlabs_tts(sentence_buffer.strip())
            else:
                sentence_buffer = ""
                try:
                    async for token in self.llm_provider.generate_stream(prompt, system_prompt=self.personality_prompt, history=self.conversation_history[:-1], temperature=temp):
                        if token:
                            await self.emit_telemetry('telemetry_llm', {"token": token, "provider": self.llm_provider.provider_name})
                            sentence_buffer += token
                            full_response_buffer.append(token)
                            if any(char in token for char in ['.', '!', '?', '\n']):
                                await self.play_tts(sentence_buffer.strip())
                                sentence_buffer = ""
                except Exception as error:
                    print(f"[Pipeline LLM Error] {error}")
                    
                if sentence_buffer.strip():
                    await self.play_tts(sentence_buffer.strip())

            final_assistant_text = "".join(full_response_buffer)
            self.conversation_history.append({"role": "assistant", "content": final_assistant_text})

            if final_assistant_text.strip():
                try:
                    from services.redis_cache import redis_cache
                    redis_cache.set(text, final_assistant_text)
                except Exception as cache_err:
                    print(f"[Redis Cache Store Error] {cache_err}", flush=True)

            await asyncio.sleep(0.5)
        finally:
            self.is_speaking = False
            await self._set_engine_state("idle")
            if self.wake_session_active:
                self._schedule_wake_session_timeout()

    async def play_tts(self, text: str):
        if not text or TTS_PROVIDER == "off":
            return

        if TTS_PROVIDER == "piper":
            await self.play_piper_tts(text)
            return

        if TTS_PROVIDER == "elevenlabs":
            await self.play_elevenlabs_tts(text)
            return

    async def play_piper_tts(self, text: str):
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
            if not audio: return

            stream = self.pa.open(
                format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True, frames_per_buffer=1024
            ) if self.native_audio_output else None
            try:
                import base64
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
        if self.elevenlabs_tts is None or self.elevenlabs_tts.voice_id != self.active_voice_id:
            from services.elevenlabs_tts import ElevenLabsTTSService
            self.elevenlabs_tts = ElevenLabsTTSService(voice_id=self.active_voice_id)
            self._update_elevenlabs_settings()

        print(f"[TTS] Sintetizando (ElevenLabs): {text}")
        await self.emit_telemetry('telemetry_tts', {"is_playing": True})
        try:
            stream = self.pa.open(
                format=pyaudio.paInt16, channels=1, rate=24000, output=True, frames_per_buffer=1024
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

    def run(self):
        self.stream = self.pa.open(
            format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True,
            frames_per_buffer=CHUNK_SIZE, stream_callback=self.audio_callback
        )
        print("[Pipeline] Micrófono Abierto.")
        self.stream.start_stream()
