import asyncio
import websockets
import json
from config import Config
from core.event_bus import EventBus
from core.state_manager import StateManager, AppState

class VADServiceAdapter:
    def __init__(self, event_bus: EventBus, state_manager: StateManager):
        self.bus = event_bus
        self.state_manager = state_manager
        self._active = False
        self.uri = Config.VAD_URI
        self.websocket = None
        self._connected = False
        
        print(f"[VADService] Initialized. Remote URI: {self.uri}")

    def start(self):
        self._active = True
        asyncio.create_task(self.connect())
        print("[VADService] Active.")

    async def connect(self):
        """Maintains a persistent connection to the VAD service."""
        while self._active:
            if not self._connected:
                try:
                    print(f"[VADService] Connecting to {self.uri}...")
                    self.websocket = await websockets.connect(self.uri)
                    self._connected = True
                    print("[VADService] Connected to remote VAD service.")
                    
                    # Listen for detection events in background
                    asyncio.create_task(self._listen())
                except Exception as e:
                    print(f"[VADService] Connection failed: {e}. Retrying in 5s...")
                    self._connected = False
                    await asyncio.sleep(5)
            else:
                await asyncio.sleep(1)

    async def _listen(self):
        """Listens for JSON events from the server."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                event_type = data.get("type")
                
                if event_type == "speech_start":
                    print("[VADService] Speech Start detected!")
                    await self.bus.emit("vad_speech_start", {})
                elif event_type == "speech_end":
                    print("[VADService] Speech End detected!")
                    await self.bus.emit("vad_speech_end", {})
        except Exception as e:
            print(f"[VADService] Listen error: {e}")
        finally:
            self._connected = False
            self.websocket = None

    def stop(self):
        self._active = False
        self._connected = False
        print("[VADService] Stopped.")

    async def process_audio(self, audio_data: bytes):
        """Sends audio chunks to the VAD service."""
        if not self._active or not self._connected or not self.websocket:
            return

        current_state = self.state_manager.get_state()
        # Only process if we care about user speech
        if current_state not in [AppState.LISTENING_USER, AppState.SPEAKING, AppState.PROCESSING]:
            return

        try:
            await self.websocket.send(audio_data)
        except Exception as e:
            print(f"[VADService] Error sending audio: {e}")
            self._connected = False
