import pyaudio
import wave
import numpy as np
import os
from dotenv import load_dotenv

# Load env manually to ensure we use current setting
load_dotenv(r"c:\Users\edgar\Documents\Proyectos2026\KodaVox\.env")

CHUNK = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "diagnostic.wav"

# Get settings from env or defaults
GAIN = float(os.getenv("MIC_GAIN", "1.0"))
INDEX = int(os.getenv("MICROPHONE_INDEX", "1"))
THRESHOLD = float(os.getenv("MIC_ENERGY_THRESHOLD", "100"))

print("="*40)
print(f"   DIAGNOSTIC RECORDING TOOL")
print("="*40)
print(f"Config:")
print(f" - Device Index: {INDEX}")
print(f" - Gain: {GAIN}x")
print(f" - Threshold: {THRESHOLD}")
print(f" - Duration: {RECORD_SECONDS}s")
print("-" * 40)

p = pyaudio.PyAudio()

try:
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=INDEX,
                    frames_per_buffer=CHUNK)

    print("\n🎤 RECORDING NOW... SPEAK! (Say 'Hello world testing')\n")

    frames = []
    
    energies = []
    
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        
        # Apply logic identical to AudioCapturer
        audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        
        # Calc raw energy before gain
        raw_energy = np.sqrt(np.mean(audio_data**2))

        # Apply Gain
        if GAIN > 1.0:
            audio_data = audio_data * GAIN
            audio_data = np.clip(audio_data, -32768, 32767)
            
        # Calc final energy
        energy = np.sqrt(np.mean(audio_data**2))
        energies.append(energy)
        
        # Convert back
        processed_data = audio_data.astype(np.int16).tobytes()
        frames.append(processed_data)
        
        # Visual bar
        bar_len = int(energy / 50)
        bar = "█" * min(bar_len, 50)
        status = "🟢" if energy > THRESHOLD else "🔴"
        print(f"RMS: {energy:6.1f} | {status} | {bar}", end="\r")

    print("\n\n🛑 Recording finished.")

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    # Stats
    avg_energy = np.mean(energies)
    max_energy = np.max(energies)
    min_energy = np.min(energies)
    
    print("-" * 40)
    print(f"ANALYSIS:")
    print(f" - Saved to: {os.path.abspath(WAVE_OUTPUT_FILENAME)}")
    print(f" - Average RMS: {avg_energy:.2f}")
    print(f" - Max RMS:     {max_energy:.2f}")
    print(f" - Min RMS:     {min_energy:.2f}")
    
    print("\nINTERPRETATION:")
    if max_energy < 50:
        print("❌ TOO QUIET: Audio is practically silent. Mic might be muted or wrong device.")
    elif max_energy < 200:
        print("⚠️ WEAK SIGNAL: Voice is very faint. Increase Gain or speak closer.")
    elif max_energy > 30000:
        print("⚠️ CLIPPING: Signal is too loud/distorted. Decrease Gain.")
    else:
        print("✅ GOOD LEVEL: Audio seems healthy.")

except Exception as e:
    print(f"\n❌ FATAL ERROR: {e}")
