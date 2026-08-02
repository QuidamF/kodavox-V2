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
from fastapi import FastAPI
from faster_whisper import WhisperModel
from contextlib import asynccontextmanager

# --- Configuración Base ---
SAMPLE_RATE = 16000
CHUNK_SIZE = 512
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
TTS_URL = os.getenv("TTS_URI", "http://127.0.0.1:8001/api/tts/stream")
TTS_CONFIG_URL = os.getenv("TTS_CONFIG_URI", "http://127.0.0.1:8001/api/config")
TTS_HEALTH_URL = os.getenv("TTS_HEALTH_URL", "http://127.0.0.1:8001/")
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
        print("[Engine] Cargando modelo Whisper Small en GPU (Modo ultra-eficiente int8_float16)...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # int8_float16 es el truco para GPUs con poca memoria pero que necesitan velocidad
        compute_type = "int8_float16" if device == "cuda" else "int8"
        
        self.stt_model = WhisperModel("small", device=device, compute_type=compute_type)
        
        self.stt_prompt = "Hola. Esta es una conversación en español latino. Se mencionan marcas como KodaVox y temas de tecnología."
        
        self.is_speaking = False
        self.audio_buffer = []
        self.pre_padding = [] 
        self.recording = False
        self.loop = None
        self.vad_threshold = 0.4

    async def setup_tts(self):
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
        if not self.is_speaking and self.loop: 
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
                    self.audio_buffer.extend(self.pre_padding)
                    self.pre_padding = []
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self.emit_telemetry('telemetry_vad', {"is_speaking": True}))
                    )
                self.audio_buffer.extend(audio_float32)
            else:
                if self.recording:
                    self.audio_buffer.extend(audio_float32)
                    self.recording = False
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self.emit_telemetry('telemetry_vad', {"is_speaking": False}))
                    )

                    if len(self.audio_buffer) > SAMPLE_RATE * 0.2:
                        audio_to_process = np.array(self.audio_buffer, dtype=np.float32)
                        self.audio_buffer = []
                        self.loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(self.process_speech(audio_to_process))
                        )
                    else:
                        self.audio_buffer = []
                else:
                    self.pre_padding.extend(audio_float32)
                    if len(self.pre_padding) > SAMPLE_RATE * 0.2:
                        self.pre_padding = self.pre_padding[-int(SAMPLE_RATE * 0.2):]

        return (in_data, pyaudio.paContinue)

    async def process_speech(self, audio_data: np.ndarray):
        print("[Engine] Transcribiendo (GPU ultra-fast)...")
        padding = np.zeros(int(SAMPLE_RATE * 0.2), dtype=np.float32)
        audio_padded = np.concatenate([audio_data, padding])

        segments, _ = self.stt_model.transcribe(
            audio_padded, 
            beam_size=5, 
            language="es",
            initial_prompt=self.stt_prompt
        )
        text = " ".join([segment.text for segment in segments]).strip()
        
        if not text or len(text) < 2 or text.lower() in ["gracias.", "continuará...", "subtitulado por"]:
            return

        print(f"[Usuario]: {text}")
        await self.emit_telemetry('telemetry_stt', {"text": text})
        await self.emit_telemetry('telemetry_llm_clear', {})
        await self.ask_ollama(text)

    async def ask_ollama(self, text: str):
        print(f"[Engine] Pensando con {OLLAMA_MODEL}...")
        self.is_speaking = True 
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"Eres un asistente de voz llamado KodaVox. Responde en español latino de forma breve y natural. Usuario: {text}",
            "stream": True
        }
        
        sentence_buffer = ""
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", OLLAMA_URL, json=payload, timeout=60.0) as response:
                    async for chunk in response.aiter_lines():
                        if chunk:
                            data = json.loads(chunk)
                            token = data.get("response", "")
                            
                            if token:
                                await self.emit_telemetry('telemetry_llm', {"token": token})
                                sentence_buffer += token
                                if any(char in token for char in ['.', '!', '?', '\n']):
                                    await self.play_tts(sentence_buffer.strip())
                                    sentence_buffer = ""
                                    
            except Exception as e:
                print(f"[Ollama Error] {e}")
                
        if sentence_buffer.strip():
            await self.play_tts(sentence_buffer.strip())

        self.is_speaking = False

    async def play_tts(self, text: str):
        if not text: return
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
socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=5000, log_level="warning")
