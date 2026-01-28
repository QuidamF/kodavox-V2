import asyncio
import websockets
import pyaudio
import numpy as np
import json
import os
from dotenv import load_dotenv

# Load env
load_dotenv(r"c:\Users\edgar\Documents\Proyectos2026\KodaVox\.env")

STT_URI = "ws://localhost:8000/api/v1/streaming"
GAIN = 4.0
CHUNK = 1280
RATE = 16000
FORMAT = pyaudio.paInt16
CHANNELS = 1

async def test_stt():
    print(f"Connecting to STT Service at {STT_URI}...")
    try:
        async with websockets.connect(STT_URI) as websocket:
            print("✅ Connected!")
            
            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            
            print("\n🎤 RECORDING 5 SECONDS... SAY 'HELLO COMPUTER'...\n")
            
            for i in range(0, int(RATE / CHUNK * 5)):
                data = stream.read(CHUNK, exception_on_overflow=False)
                
                # Apply Gain matching Orchestrator logic
                audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                audio_data = audio_data * GAIN
                audio_data = np.clip(audio_data, -32768, 32767)
                processed_data = audio_data.astype(np.int16).tobytes()
                
                # Send
                await websocket.send(processed_data)
                print(".", end="", flush=True)

            print("\n\n🛑 Stopping and waiting for transcription...")
            await websocket.send(json.dumps({"action": "stop"}))
            
            response = await websocket.recv()
            print(f"\n📩 RESPONSE: {response}")
            
            data = json.loads(response)
            transcript = data.get("transcription") or data.get("transcript")
            
            if transcript:
                print(f"\n✅ SUCCESS: '{transcript}'")
            else:
                print(f"\n⚠️ EMPTY: STT returned text but it was empty.")

            stream.stop_stream()
            stream.close()
            p.terminate()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_stt())
