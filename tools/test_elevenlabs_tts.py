import asyncio
import sys
import os
import pyaudio

# Permitir importar la carpeta orchestrator desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from orchestrator.services.elevenlabs_tts import ElevenLabsTTSService


async def test_elevenlabs(text: str):
    print("\n--- Probando Servicio ElevenLabs TTS ---")
    service = ElevenLabsTTSService()
    print(f"Voice ID: {service.voice_id}")
    print(f"Model ID: {service.model_id}")
    print(f"Sintetizando: \"{text}\"\n")

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=24000,
        output=True,
        frames_per_buffer=1024,
    )

    chunk_count = 0
    total_bytes = 0
    try:
        async for chunk in service.stream_audio_pcm(text):
            if chunk:
                chunk_count += 1
                total_bytes += len(chunk)
                await asyncio.to_thread(stream.write, chunk)
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

    print(f"\n[Síntesis completada - {chunk_count} chunks, {total_bytes} bytes reproducidos]\n")


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Hola KodaVox, esta es una prueba de voz de alta fidelidad con ElevenLabs."
    asyncio.run(test_elevenlabs(prompt))
