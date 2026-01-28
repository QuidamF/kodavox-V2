import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
import sys
import time
from dotenv import load_dotenv

# Cargar configuración
load_dotenv()

RATE = int(os.getenv("SAMPLE_RATE", "16000"))
CHANNELS = 1
DURATION = 5  # Segundos
FILENAME = "test_capture.wav"

def list_devices():
    print("\n--- Dispositivos de Audio Disponibles (SoundDevice) ---")
    print(sd.query_devices())
    print("-------------------------------------------------------\n")

def main():
    print(f"Probando micrófono con SoundDevice...")
    list_devices()
    
    # Intentar obtener el índice del .env, pero sounddevice usa índices diferentes a veces que pyaudio
    # Por defecto usará el default del sistema si no especificamos, o podemos intentar mapear.
    # Para la prueba, recomendaremos usar el default primero.
    
    print(f"Configuración:")
    print(f"  Sample Rate: {RATE}")
    print(f"  Duración: {DURATION} segundos")
    print(f"  Canales: {CHANNELS}")
    
    print(f"\n[GRABANDO] Habla fuerte ahora... (5s)")
    
    try:
        # Grabar
        recording = sd.rec(int(DURATION * RATE), samplerate=RATE, channels=CHANNELS, dtype='int16')
        sd.wait()  # Esperar a que termine
        print("[FIN] Grabación terminada.")
        
        # Guardar
        wav.write(FILENAME, RATE, recording)
        print(f"Audio guardado en: {FILENAME}")
        
        # Calcular energía (RMS) para diagnóstico
        # Convertir a float para evitar overflow al elevar al cuadrado
        data_float = recording.astype(np.float64)
        rms = np.sqrt(np.mean(data_float**2))
        print(f"Nivel de Energía Promedio (RMS): {rms:.2f}")
        
        if rms < 10:
            print("⚠️ ADVERTENCIA: La señal es EXTREMADAMENTE baja. Es posible que el micrófono no esté captando nada.")
        elif rms < 100:
            print("⚠️ ADVERTENCIA: La señal es bastante baja. Podría necesitar ganancia.")
        else:
            print("✅ Señal detectada con buen nivel.")

        # Reproducir
        print("\n[REPRODUCIENDO] Escucha tu voz...")
        sd.play(recording, RATE)
        sd.wait()
        print("[FIN] Reproducción terminada.")

    except Exception as e:
        print(f"[ERROR] Falló la grabación/reproducción: {e}")

if __name__ == "__main__":
    main()
