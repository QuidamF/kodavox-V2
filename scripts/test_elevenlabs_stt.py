import asyncio
import os
import sys
import time
import argparse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from services.elevenlabs_stt import ElevenLabsSTTService

async def test_elevenlabs_stt(audio_file_path: str = None):
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("[ERROR] No se encontró ELEVENLABS_API_KEY en las variables de entorno (.env).")
        return

    stt = ElevenLabsSTTService(api_key=api_key)
    
    if audio_file_path and os.path.exists(audio_file_path):
        print(f"--- Probando ElevenLabs STT con archivo real: {audio_file_path} ---")
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()
        
        start_time = time.time()
        
        # Si ya es un WAV o MP3, enviarlo directamente o procesar
        if audio_file_path.endswith(".wav") or audio_file_path.endswith(".mp3"):
            import httpx
            headers = {"xi-api-key": api_key}
            data = {"model_id": stt.model_id, "language_code": "spa"}
            files = {"file": (os.path.basename(audio_file_path), audio_bytes, "audio/wav")}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(stt.url, headers=headers, data=data, files=files, timeout=30.0)
                elapsed = time.time() - start_time
                if response.status_code == 200:
                    res_json = response.json()
                    print(f"⏱️ Tiempo transcurrido: {elapsed:.2f}s")
                    print(f"🗣️ Transcripción: '{res_json.get('text', '')}'")
                else:
                    print(f"❌ Error HTTP {response.status_code}: {response.text}")
        else:
            result = await stt.transcribe_audio_bytes(audio_bytes, sample_rate=16000, language_code="spa")
            elapsed = time.time() - start_time
            print(f"⏱️ Tiempo transcurrido: {elapsed:.2f}s")
            print(f"🗣️ Transcripción: '{result}'")
    else:
        print("--- Probando ElevenLabs STT con audio generado (Dummy) ---")
        sample_rate = 16000
        dummy_pcm = b'\x00\x00' * (sample_rate * 2)

        start_time = time.time()
        result = await stt.transcribe_audio_bytes(dummy_pcm, sample_rate=sample_rate, language_code="spa")
        elapsed = time.time() - start_time
        print(f"⏱️ Tiempo transcurrido: {elapsed:.2f}s")
        print(f"🗣️ Resultado transcripción: '{result}'")
    
    print("--- Prueba finalizada ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba de ElevenLabs STT")
    parser.add_argument("--file", type=str, help="Ruta a un archivo de audio (.wav/.mp3) para probar transcripción real")
    args = parser.parse_args()
    
    asyncio.run(test_elevenlabs_stt(args.file))
