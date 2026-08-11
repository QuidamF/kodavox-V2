import asyncio
import os
import time
from dotenv import load_dotenv

load_dotenv()

from orchestrator.services.llm_provider import LLMFactory
from orchestrator.services.elevenlabs_tts import ElevenLabsTTSService

async def test():
    print("Testing Gemini -> ElevenLabs streaming latency...")
    llm = LLMFactory.get_provider()
    tts = ElevenLabsTTSService()
    
    prompt = "Cuentame un chiste muy corto de un pepito"
    
    start_time = time.time()
    
    async def token_gen():
        first_token_time = None
        async for token in llm.generate_stream(prompt):
            if token:
                if not first_token_time:
                    first_token_time = time.time()
                    print(f"\n[Latencia LLM] Primer token en {first_token_time - start_time:.2f}s: '{token}'")
                yield token
                
    
    first_audio_time = None
    bytes_received = 0
    
    async for chunk in tts.stream_input_pcm(token_gen()):
        if not first_audio_time:
            first_audio_time = time.time()
            print(f"[Latencia TTS] Primer audio recibido en {first_audio_time - start_time:.2f}s")
        bytes_received += len(chunk)
        
    end_time = time.time()
    print(f"\nTerminado en {end_time - start_time:.2f}s. Audio bytes: {bytes_received}")

asyncio.run(test())
