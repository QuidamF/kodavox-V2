import requests
import asyncio
import websockets
import json
from config import Config

def check_http_service(name, url):
    print(f"[*] Checking {name} at {url}...", end=" ")
    try:
        # Intentar una petición simple o GET /
        response = requests.get(url.replace("/ask", "/").replace("/api/tts/stream", "/"), timeout=3)
        if response.status_code < 500:
            print("✅ ONLINE")
            return True
        else:
            print(f"⚠️ SERVER ERROR ({response.status_code})")
    except Exception as e:
        print(f"❌ OFFLINE ({e})")
    return False

async def check_ws_service(name, url):
    print(f"[*] Checking {name} at {url}...", end=" ")
    try:
        async with websockets.connect(url, open_timeout=3) as ws:
            print("✅ ONLINE")
            return True
    except Exception as e:
        print(f"❌ OFFLINE ({e})")
    return False

async def run_checks():
    print("=== Service Health Check ===")
    check_http_service("RAG Service", Config.RAG_URI)
    check_http_service("TTS Service", Config.TTS_URI)
    await check_ws_service("STT Service", Config.STT_URI)
    print("============================\n")
    print("Si todos están Online, puedes correr: python main.py")

if __name__ == "__main__":
    asyncio.run(run_checks())
