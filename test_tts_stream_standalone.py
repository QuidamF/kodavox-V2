import requests
import pyaudio
import json
import os
import sys

# URL del servicio TTS (Directo al puerto de Docker)
TTS_URL = "http://localhost:8001/api/tts/stream"
BATCH_URL = "http://localhost:8001/api/tts/batch"
HEALTH_URL = "http://localhost:8001/"

def check_health():
    print(f"Checking {HEALTH_URL}...")
    try:
        r = requests.get(HEALTH_URL, timeout=2)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error checking health: {e}")
        return False

def test_stream_and_play():
    print(f"\nTesting Stream from {TTS_URL}...")
    
    # 1. Setup PyAudio
    p = pyaudio.PyAudio()
    output_device_index = None # Use default
    
    # List devices to be sure
    print("\nAudio Devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxOutputChannels'] > 0:
            print(f"  [{i}] {info['name']}")
    
    try:
        # Configurar stream de PyAudio (24kHz, Mono, 16-bit)
        stream_player = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,
            output=True,
            output_device_index=output_device_index
        )
    except Exception as e:
        print(f"Failed to open PyAudio stream: {e}")
        return

    # 2. Configurar Payload
    # Asegúrate de que 'voice_sample' coincida con uno existente o el config
    payload = {
        "text": "Esta es una prueba de audio directo desde el script de depuración.",
        "stream": True
    }
    
    # Intentar obtener config actual del servicio
    try:
        r_conf = requests.get(HEALTH_URL)
        config = r_conf.json().get("config", {})
        if config.get("voice_sample"):
            print(f"Using voice from config: {config['voice_sample']}")
            # Note: The Endpoint usually reads from internal config if not provided, 
            # but we can try just sending text.
    except:
        pass

    print("\nSending Request...")
    try:
        with requests.post(TTS_URL, json=payload, stream=True) as response:
            if response.status_code != 200:
                print(f"Error Request: {response.status_code} - {response.text}")
                return

            print("Stream Connected. Receiving chunks...")
            chunk_count = 0
            total_bytes = 0
            
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    chunk_count += 1
                    total_bytes += len(chunk)
                    # Play chunk
                    stream_player.write(chunk)
                    sys.stdout.write(f"\rChunks: {chunk_count} | Bytes: {total_bytes}")
                    sys.stdout.flush()
            
            print("\n\nStream Finished.")
            
    except Exception as e:
        print(f"\nStream Error: {e}")
    finally:
        stream_player.stop_stream()
        stream_player.close()
        p.terminate()

if __name__ == "__main__":
    if check_health():
        test_stream_and_play()
    else:
        print("TTS Service seems offline.")
