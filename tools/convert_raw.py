import wave
import os

RAW_FILE = "debug_sent_audio.raw"
WAV_FILE = "debug_check.wav"

if not os.path.exists(RAW_FILE):
    print(f"❌ Error: {RAW_FILE} not found. Did you run the Orchestrator and speak?")
    exit()

with open(RAW_FILE, "rb") as f:
    raw_data = f.read()

if len(raw_data) == 0:
    print("❌ Error: File is empty (0 bytes). No audio was captured/sent.")
    exit()

print(f"✅ Found {len(raw_data)} bytes of raw audio.")

try:
    with wave.open(WAV_FILE, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) # 16-bit
        wf.setframerate(16000)
        wf.writeframes(raw_data)
        
    print(f"✅ Converted to: {os.path.abspath(WAV_FILE)}")
    print("👉 Please open this file and LISTEN.")
    print("   - If it's silent: The Orchestrator/Mic is sending silence.")
    print("   - If it's static: The Orchestrator is corrupting data.")
    print("   - If it's clear voice: The Orchestrator is innocent, the STT Docker is guilty.")

except Exception as e:
    print(f"❌ Error writing WAV: {e}")
