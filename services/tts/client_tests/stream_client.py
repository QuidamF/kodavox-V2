import requests
import json
import sys
import time

# Try importing pyaudio for real-time playback
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("Warning: 'pyaudio' not found. Audio will be saved to file but not played in real-time.")
    print("To enable playback: pip install pyaudio")

# --- Configuration ---
DEFAULT_API_URL = "http://localhost:8000/api/tts/stream"
# These settings match XTTS v2 output
SAMPLE_RATE = 24000
CHANNELS = 1
FORMAT = pyaudio.paInt16 if PYAUDIO_AVAILABLE else None

def stream_audio(text, voice_sample=None, language="es", api_url=DEFAULT_API_URL, output_file="stream_output.wav"):
    
    # 1. Setup PyAudio stream (if available)
    p = None
    stream = None
    play_audio = PYAUDIO_AVAILABLE # Local flag

    if play_audio:
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=SAMPLE_RATE,
                            output=True)
            print("--- Audio Device Initialized ---")
        except Exception as e:
            print(f"Error initializing audio device: {e}")
            play_audio = False # Disable playback for this run only

    # 2. Prepare Request
    headers = {"Content-Type": "application/json"}
    payload = {
        "text": text,
        "language": language
    }
    if voice_sample:
        payload["voice_sample"] = voice_sample

    print(f"--- Sending request to {api_url} ---")
    
    try:
        # stream=True is critical here!
        with requests.post(api_url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()
            
            print("--- Receiving Audio Stream ---")
            # Open file for saving raw audio
            with open(output_file, 'wb') as f:
                # Iterate over chunks. 
                # chunk_size=1024 is arbitrary, but good for networking.
                # The server sends audio chunks as they are generated.
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        # Play
                        if play_audio and stream:
                            stream.write(chunk)
                        # Save
                        f.write(chunk)
            
            print("\n--- Stream Finished ---")
            print(f"Audio saved to: {output_file}")

    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        # Cleanup
        if p:
            if stream:
                stream.stop_stream()
                stream.close()
            p.terminate()

if __name__ == "__main__":
    # Example usage
    sample_text = (
        "Hola. Esta es una demostración del nuevo sistema de streaming optimizado. "
        "Como puedes escuchar, el audio se genera y reproduce frase por frase. "
        "Esto permite leer textos muy largos sin que el servidor se sature o la voz se distorsione. "
        "¡Espero que te guste el resultado!"
    )
    
    # Get config from args or use defaults
    api_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_API_URL
    
    print("--- TTS Stream Client ---")
    voice = input("Enter voice filename (leave empty to use server default): ").strip()
    text = input(f"Enter text (default: '{sample_text[:20]}...'): ").strip() or sample_text
    
    stream_audio(text, voice_sample=voice if voice else None, api_url=api_url)
