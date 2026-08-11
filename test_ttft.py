import asyncio
import os
import time
from dotenv import load_dotenv

load_dotenv()
from orchestrator.services.llm_provider import OpenAIProvider, GeminiProvider

async def test_ttft():
    prompt = "Cuentame un chiste muy corto"
    
    print("Testing OpenAI...")
    openai = OpenAIProvider()
    start = time.time()
    try:
        async for t in openai.generate_stream(prompt):
            if t:
                print(f"OpenAI TTFT: {time.time()-start:.3f}s")
                break
    except Exception as e:
        print("OpenAI error:", e)
        
    print("Testing Gemini...")
    gemini = GeminiProvider()
    start = time.time()
    try:
        async for t in gemini.generate_stream(prompt):
            if t:
                print(f"Gemini TTFT: {time.time()-start:.3f}s")
                break
    except Exception as e:
        print("Gemini error:", e)

asyncio.run(test_ttft())
