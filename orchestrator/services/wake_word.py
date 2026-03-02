import asyncio
import websockets
import json
import logging
from config import Config
from core.event_bus import EventBus
from core.state_manager import StateManager, AppState

class WakeWordService:
    def __init__(self, event_bus: EventBus, state_manager: StateManager):
        self.bus = event_bus
        self.state_manager = state_manager
        self._active = False
        self.uri = Config.WAKEWORD_URI
        self.websocket = None
        self._connected = False
        
        print(f"[WakeWordService] Initialized. Remote URI: {self.uri}")

    def start(self):
        self._active = True
        # We don't connect immediately here because we'll connect/reconnect as needed
        # OR we could start an connection loop. Given it's a critical always-on service,
        # let's try to maintain a connection.
        asyncio.create_task(self.connect())
        print("[WakeWordService] Active.")

    async def connect(self):
        """Maintains a persistent connection to the wakeword service."""
        while self._active:
            if not self._connected:
                try:
                    print(f"[WakeWordService] Connecting to {self.uri}...")
                    self.websocket = await websockets.connect(self.uri)
                    self._connected = True
                    print("[WakeWordService] Connected to remote Wake Word service.")
                    
                    # Listen for detection events in background
                    asyncio.create_task(self._listen())
                except Exception as e:
                    print(f"[WakeWordService] Connection failed: {e}. Retrying in 5s...")
                    self._connected = False
                    await asyncio.sleep(5)
            else:
                await asyncio.sleep(1)

    async def _listen(self):
        """Listens for JSON events from the server."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data.get("event") == "detected":
                    score = data.get("score", 1.0)
                    print(f"[WakeWordService] Wake Word Detected by remote! ({score:.2f})")
                    await self.bus.emit("wakeword_detected", {"score": float(score)})
        except Exception as e:
            print(f"[WakeWordService] Listen error: {e}")
        finally:
            self._connected = False
            self.websocket = None

    def stop(self):
        self._active = False
        self._connected = False
        print("[WakeWordService] Stopped.")

    async def process_audio(self, audio_data: bytes):
        """Sends audio chunks to the remote service for detection."""
        if not self._active or not self._connected or not self.websocket:
            return

        # Optimization: Only process if orchestrator is in a state that expects wake word
        current_state = self.state_manager.get_state()
        if current_state not in [AppState.IDLE, AppState.LISTENING_WAKEWORD]:
            return

        try:
            await self.websocket.send(audio_data)
        except Exception as e:
            print(f"[WakeWordService] Error sending audio: {e}")
            self._connected = False
