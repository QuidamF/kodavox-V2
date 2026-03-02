from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.services.detector import WakeWordDetector
import os
import json

app = FastAPI(title="Wake Word Service")

# Load config from env
MODEL_NAME = os.getenv("WAKEWORD_MODEL", "hey_jarvis")
THRESHOLD = float(os.getenv("WAKEWORD_THRESHOLD", "0.5"))

# Initialize detector (singleton-ish for the app)
detector = WakeWordDetector(MODEL_NAME, THRESHOLD)

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}

@app.websocket("/streaming")
async def streaming_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WS] Client connected for wake word detection.")
    
    try:
        while True:
            # Receive audio chunk as bytes
            data = await websocket.receive_bytes()
            
            # Process with detector
            detected = detector.process_frame(data)
            
            if detected:
                # Notify client
                await websocket.send_json({"event": "detected", "score": 1.0})
                
    except WebSocketDisconnect:
        print("[WS] Client disconnected.")
    except Exception as e:
        print(f"[WS] Error: {e}")
        await websocket.close()
