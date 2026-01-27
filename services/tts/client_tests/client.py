import requests
import json
import os
import sys # Import sys for command-line arguments
# import wave # Not needed for raw PCM

# --- Configuration ---
API_URL = "http://192.168.209.1:8000/api/tts/stream" # Ajusta esta IP si tu host tiene otra.
VOICE_SAMPLE_FILENAME = "my_voice_sample.mp3" # Asegúrate de que este archivo exista en tu carpeta 'voices' del HOST
TEXT_TO_SPEAK = "Hola, esta es una prueba de streaming de audio en tiempo real desde el servicio TTS."
LANGUAGE = "es"
OUTPUT_FILENAME = "client_output.pcm" # Ahora guardaremos como RAW PCM

# --- Audio settings (should match the TTS model output) ---
# XTTSv2 outputs at 24kHz sample rate, 16-bit PCM
SAMPLE_RATE = 24000
# FORMAT_WIDTH = 2 # 2 bytes for 16-bit audio (corresponds to paInt16) - no longer directly used but good to keep for reference
CHANNELS = 1 # XTTS output is mono

def stream_and_save(api_url): # Corrected function definition
    print(f"--- Sending request to {api_url} ---") # Now uses the passed argument
    print(f"Text: '{TEXT_TO_SPEAK}'")
    print(f"Voice Sample: '{VOICE_SAMPLE_FILENAME}'")
    
    # This warning is more for clarity when running on the host.
    # When run INSIDE the VM, it's about the VM's local client script's perspective.
    # The actual server side voice sample existence is handled by the server.
    print(f"INFO: Asegúrate de que el archivo de voz '{VOICE_SAMPLE_FILENAME}' exista en el directorio 'voices' de tu MÁQUINA ANFITRIONA.")

    headers = {"Content-Type": "application/json"}
    payload = {
        "text": TEXT_TO_SPEAK,
        "voice_sample": VOICE_SAMPLE_FILENAME,
        "language": LANGUAGE,
    }

    output_file = None

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload), stream=True)
        response.raise_for_status() # Raise an exception for bad status codes

        print(f"--- Connected to audio stream. Saving to '{OUTPUT_FILENAME}' ---")
        
        # Open file directly for binary writing
        output_file = open(OUTPUT_FILENAME, 'wb')

        for chunk in response.iter_content(chunk_size=1024): # Adjust chunk_size as needed
            if chunk: # Filter out keep-alive chunks
                output_file.write(chunk)

        print(f"--- Audio stream finished. Saved to '{OUTPUT_FILENAME}'. ---")

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión o HTTP: {e}")
        if response is not None:
            print(f"Server response content: {response.text}")
    except Exception as e:
        print(f"Error durante el guardado del audio: {e}")
    finally:
        if output_file is not None:
            output_file.close()

if __name__ == "__main__":
    # Removed hardcoded API_URL definition from here, as it's now an argument to stream_and_save
    default_api_url = "http://192.168.209.1:8000/api/tts/stream" # Ejemplo de IP del host
    if len(sys.argv) > 1:
        api_url_to_use = sys.argv[1]
    else:
        api_url_to_use = default_api_url
        print(f"No se proporcionó API_URL. Usando por defecto: {default_api_url}")
        print("Puedes proporcionar la URL como argumento: python client.py http://<IP_DE_TU_HOST>:8000/api/tts/stream")

    print("Iniciando cliente de streaming TTS (modo guardar a archivo RAW PCM).")
    print("Asegúrate de que el servidor Docker esté corriendo en la IP especificada en API_URL.")
    
    input("\nPresiona Enter para comenzar el streaming y guardar el audio...")
    stream_and_save(api_url_to_use)
    print("Cliente TTS finalizado.")
