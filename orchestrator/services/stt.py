import asyncio
import websockets
import json
import logging
from config import Config
from core.event_bus import EventBus

class STTServiceAdapter:
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self.uri = Config.STT_URI
        self.websocket = None
        self._connected = False
        self._bytes_sent = 0

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            self._connected = True
            self._bytes_sent = 0
            # Clean debug file
            import os
            if os.path.exists("debug_sent_audio.raw"):
                os.remove("debug_sent_audio.raw")
            print("[STTService] Connected to WebSocket.")
        except Exception as e:
            print(f"[STTService] Connection failed: {e}")
            self._connected = False

    async def send_audio(self, audio_chunk: bytes):
        if not self._connected or not self.websocket:
            return
        try:
            await self.websocket.send(audio_chunk)
            self._bytes_sent += len(audio_chunk)
            
            # DEBUG: Save to local file to verify what we are sending
            with open("debug_sent_audio.raw", "ab") as f:
                f.write(audio_chunk)

        except Exception as e:
            print(f"[STTService] Error sending audio: {e}")

    async def stop_and_get_result(self) -> str:
        if not self._connected or not self.websocket:
            return ""
        
        try:
            print(f"[STTService] Sending stop signal... (Sent {self._bytes_sent} bytes total)")
            await self.websocket.send(json.dumps({"action": "stop"}))
            response = await self.websocket.recv()
            data = json.loads(response)
            transcription = data.get("transcript", "")
            print(f"[STTService] Transcription received: {transcription}")
            
            await self.websocket.close()
            self._connected = False
            self.websocket = None
            
            return transcription
        except Exception as e:
            print(f"[STTService] Error receiving result: {e}")
            return ""
