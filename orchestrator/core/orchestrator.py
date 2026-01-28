import asyncio
import threading
from config import Config
from core.event_bus import EventBus
from core.state_manager import StateManager, AppState
from core.audio_capture import AudioCapturer
from services.wake_word import WakeWordService
from services.stt import STTServiceAdapter
from services.rag import RAGServiceAdapter
from services.tts import TTSServiceAdapter

class VoiceOrchestrator:
    def __init__(self, event_bus: EventBus, state_manager: StateManager):
        self.bus = event_bus
        self.state_manager = state_manager
        
        # Inicializar capturador
        self.capturer = AudioCapturer(self.bus)
        
        # Inicializar servicios
        self.ww_service = WakeWordService(self.bus, self.state_manager)
        self.stt_service = STTServiceAdapter(self.bus)
        self.rag_service = RAGServiceAdapter()
        self.tts_service = TTSServiceAdapter()

        self._loop = None
        self._silence_counter = 0
        self._max_silence_chunks = 35 # ~2.8 segundos de silencio para cortar (increased)

        # Registrar eventos
        self.bus.on("wakeword_detected", self.handle_wakeword)
        self.bus.on("audio_chunk", self.handle_audio)
        
        # Eventos de Debug / Control Manual
        self.bus.on("manual_listen", self.handle_manual_listen)
        self.bus.on("process_text", self.handle_process_text)
        self.bus.on("speak_text", self.handle_speak_text)
        self.bus.on("query_rag", self.handle_query_rag)

    def start(self):
        """Inicia el orquestador."""
        print("[Orchestrator] Starting...")
        self._loop = asyncio.get_event_loop()
        
        # Iniciar captura y detección de wake word
        self.capturer.start(self._loop)
        self.ww_service.start()
        
        asyncio.run_coroutine_threadsafe(
            self.state_manager.set_state(AppState.LISTENING_WAKEWORD), 
            self._loop
        )

    async def handle_audio(self, data):
        """Maneja cada chunk de audio emitido por el capturador."""
        chunk = data["data"]
        energy = data["energy"]
        state = self.state_manager.get_state()

        # Enviar al buscador de palabra clave si está activo
        if state in [AppState.IDLE, AppState.LISTENING_WAKEWORD]:
            await self.ww_service.process_audio(chunk)

        # Enviar al STT si estamos escuchando al usuario
        if state == AppState.LISTENING_USER:
            # print(".", end="", flush=True) # visual heartbeat
            await self.stt_service.send_audio(chunk)
            
            # Detección de silencio para terminar la frase
            if energy < Config.MIC_ENERGY_THRESHOLD: # Threshold de silencio configurado
                self._silence_counter += 1
                if self._silence_counter % 5 == 0:
                     print(f"[Orchestrator] Silence: {self._silence_counter}/{self._max_silence_chunks} (Energy: {energy:.1f})")
            else:
                if self._silence_counter > 0:
                     print(f"[Orchestrator] Voice! Resetting silence. (Energy: {energy:.1f})")
                self._silence_counter = 0
            
            if self._silence_counter > self._max_silence_chunks:
                print(f"[Orchestrator] Max silence reached ({self._max_silence_chunks} chunks). unprocessed.")
                print("[Orchestrator] Silence detected, finishing speech capture.")
                self._silence_counter = 0
                # Disparar el procesamiento en una tarea separada para no bloquear
                asyncio.create_task(self.process_interaction())

    async def handle_wakeword(self, data):
        """Manejador disparado cuando se detecta la palabra clave."""
        print(f"[Orchestrator] handle_wakeword triggered. State: {self.state_manager.get_state()}")
        try:
            if self.state_manager.get_state() != AppState.LISTENING_WAKEWORD:
                print("[Orchestrator] Ignoring wake word (not listening)")
                return

            print("[Orchestrator] Wake word detected! Starting interaction.")
            await self.state_manager.set_state(AppState.LISTENING_USER)
            self._silence_counter = 0
            await self.stt_service.connect()
        except Exception as e:
            print(f"[Orchestrator] CRITICAL ERROR in handle_wakeword: {e}")
            import traceback
            traceback.print_exc()

    async def handle_manual_listen(self, data):
        """Fuerza al sistema al estado de escucha de usuario."""
        print("[Orchestrator] Manual listen triggered.")
        await self.state_manager.set_state(AppState.LISTENING_USER)
        self._silence_counter = 0
        await self.stt_service.connect()

    async def handle_process_text(self, data):
        """Procesa texto directamente como si hubiera sido escuchado."""
        text = data.get("text", "")
        if text:
            print(f"[Orchestrator] Processing manual text: {text}")
            # Simulamos estado de escucha para que process_interaction no rechace
            await self.state_manager.set_state(AppState.LISTENING_USER) 
            await self.process_interaction(text=text)

    async def handle_speak_text(self, data):
        """Sintetiza texto directamente."""
        text = data.get("text", "")
        if text:
            print(f"[Orchestrator] Manual TTS: {text}")
            await asyncio.to_thread(self.tts_service.speak, text)

    async def handle_query_rag(self, data):
        """Consulta RAG directamente."""
        text = data.get("text", "")
        if text:
            print(f"[Orchestrator] Manual RAG query: {text}")
            response = await asyncio.to_thread(self.rag_service.query, text)
            await self.bus.emit("rag_response", {"text": response})

    async def process_interaction(self, text=None):
        """Coordina el procesamiento del audio capturado o texto inyectado."""
        if self.state_manager.get_state() != AppState.LISTENING_USER:
            return

        try:
            await self.state_manager.set_state(AppState.PROCESSING)
            
            # 1. Obtener transcripción (si no se proveyó texto)
            if text is None:
                text = await self.stt_service.stop_and_get_result()
            
            if not text or len(text.strip()) < 2:
                print("[Orchestrator] No valid speech detected.")
                await self.state_manager.set_state(AppState.LISTENING_WAKEWORD)
                return

            print(f"[Orchestrator] User said: {text}")
            await self.bus.emit("transcription_final", {"text": text})

            # 2. Consultar RAG
            response_text = await asyncio.to_thread(self.rag_service.query, text)
            await self.bus.emit("rag_response", {"text": response_text})

            # 3. Sintetizar respuesta (TTS)
            await self.state_manager.set_state(AppState.SPEAKING)
            # Enviar feedback de voz
            await asyncio.to_thread(self.tts_service.speak, response_text)

            # 4. Volver a esperar
            print("[Orchestrator] Resuming wake word detection.")
            await self.state_manager.set_state(AppState.LISTENING_WAKEWORD)

        except Exception as e:
            print(f"[Orchestrator] Error during interaction: {e}")
            await self.state_manager.set_state(AppState.ERROR)
            await asyncio.sleep(2)
            await self.state_manager.set_state(AppState.LISTENING_WAKEWORD)
