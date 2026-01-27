import asyncio
import argparse
import json
import os
import sys

# Try to import required libraries
try:
    import requests
    import websockets
    import numpy as np
    import soundfile as sf
except ImportError:
    print("Missing dependencies. Please run: pip install requests websockets numpy soundfile")
    sys.exit(1)

API_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8000/api/v1/streaming"

def create_test_audio(filename="test.wav", duration=3):
    print(f"Generating test audio file: {filename}...")
    samplerate = 16000
    frequency = 440
    t = np.linspace(0., duration, int(samplerate * duration), endpoint=False)
    amplitude = np.iinfo(np.int16).max * 0.5
    data = amplitude * np.sin(2. * np.pi * frequency * t)
    sf.write(filename, data.astype(np.int16), samplerate)
    print("Audio file generated.")

def test_rest_api(filename="test.wav"):
    print("\n--- Testing REST API ---")
    url = f"{API_URL}/transcribe"
    files = {'audio_file': open(filename, 'rb')}
    try:
        response = requests.post(url, files=files)
        if response.status_code == 200:
            print("Success!")
            print("Response:", response.json())
        else:
            print(f"Failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error testing REST API: {e}")

async def test_websocket_api(filename="test.wav"):
    print("\n--- Testing WebSocket API ---")
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("Connected to WebSocket.")
            
            # Send audio bytes
            with open(filename, "rb") as f:
                audio_data = f.read()
                # Simulate streaming in chunks
                chunk_size = 4096
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i+chunk_size]
                    await websocket.send(chunk)
                    # small delay to simulate real-time
                    await asyncio.sleep(0.01)
            
            print("Audio sent. Sending stop command...")
            await websocket.send(json.dumps({"action": "stop"}))
            
            response = await websocket.recv()
            print("Response:", response)
            
    except Exception as e:
        print(f"Error testing WebSocket API: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test STT API")
    parser.add_argument("--file", type=str, default="test.wav", help="Audio file to test")
    args = parser.parse_args()

    if not os.path.exists(args.file) and args.file == "test.wav":
        create_test_audio(args.file)

    if not os.path.exists(args.file):
        print(f"File {args.file} not found.")
        sys.exit(1)

    # Test REST
    test_rest_api(args.file)

    # Test WebSocket (needs asyncio)
    asyncio.run(test_websocket_api(args.file))
