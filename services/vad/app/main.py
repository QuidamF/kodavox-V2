from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.services.vad_service import SileroVADService
import json

app = FastAPI(title="VAD Service (Voice Activity Detection)")

# Initialize VAD Service (Singleton-ish per worker)
vad_detector = SileroVADService()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "VAD"}

@app.websocket("/streaming")
async def streaming_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WS] Client connected for VAD streaming.")
    
    try:
        while True:
            # Receive binary audio chunk
            # The client should send raw bytes (e.g. 512 bytes per frame)
            audio_chunk = await websocket.receive_bytes()
            
            # Process chunk with VAD
            events = await vad_detector.process_chunk(audio_chunk)
            
            # Send back events if any occurred
            for event in events:
                if event["type"] in ["speech_start", "speech_end"]:
                    await websocket.send_json(event)
                elif event["type"] == "speech_frame":
                    # Optionally, we don't send the audio data back to save bandwidth,
                    # just an acknowledgment, or the orchestrator routes it directly.
                    # The VAD acts merely as a state machine.
                    await websocket.send_json({"type": "speech_frame"})
                    
    except WebSocketDisconnect:
        print("[WS] Client disconnected.")
    except Exception as e:
        print(f"[WS] Error: {e}")
        await websocket.close()
