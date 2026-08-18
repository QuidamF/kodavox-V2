import asyncio
import os
import sys
import time
from dotenv import load_dotenv

# Cargar variables de entorno desde el directorio orchestrator o raíz
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from services.elevenlabs_stt import ElevenLabsSTTService

async def test_elevenlabs_stt():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("[ERROR] No se encontró ELEVENLABS_API_KEY en las variables de entorno.")
        print("Por favor, asegúrate de tener configurada la variable ELEVENLABS_API_KEY en tu .env")
        return

    stt = ElevenLabsSTTService(api_key=api_key)
    
    # Generar 2 segundos de audio de silencio/PCM de prueba si no hay archivo
    sample_rate = 16000
    dummy_pcm = b'\x00\x00' * (sample_rate * 2)

    print("--- Iniciando prueba de ElevenLabs STT ---")
    start_time = time.time()
    
    # Llamada al API
    result = await stt.transcribe_audio_bytes(dummy_pcm, sample_rate=sample_rate, language_code="spa")
    
    elapsed = time.time() - start_time
    print(f"Tiempo transcurrido: {elapsed:.2f}s")
    print(f"Resultado de transcripción: '{result}'")
    print("--- Prueba finalizada ---")

if __name__ == "__main__":
    asyncio.run(test_elevenlabs_stt())
