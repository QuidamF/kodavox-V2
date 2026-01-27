import os
import time
import threading
import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
from dotenv import load_dotenv

#from gtts import gTTS
#from google.cloud import texttospeech

import requests

# Cargar variables desde .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPEECH_KEY = os.getenv("SPEECH_KEY")
SPEECH_REGION = os.getenv("SPEECH_REGION")

# Configurar OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Configurar reconocimiento de voz en Azure
speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
speech_config.speech_recognition_language = "es-MX"

# Definir la wake word y el modelo
WAKE_WORD = "Ok Robot"
MODEL_PATH = "models/v_advanced.table"

listening = False
wake_word_active = True
lock = threading.Lock()

def sendStatusFace(status):
    import requests

    url = "http://localhost:9020/v1/face/state"

    payload = {"Command": status}
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.request("POST", url, json=payload, headers=headers)

    print(response.text)

def recognize_from_microphone():
    """Escucha una frase después de detectar la wake word y devuelve el texto."""
    global wake_word_active
    wake_word_active = False  # Pausar la detección de la wake word mientras escucha al usuario

    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    sendStatusFace("c")
    print("🎤 Escuchando...")
    result = recognizer.recognize_once_async().get()

    wake_word_active = True  # Reactivar la wake word después del reconocimiento de voz

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"✅ Reconocido: {result.text}")
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("⚠ No se reconoció ninguna voz.")
    elif result.reason == speechsdk.ResultReason.Canceled:
        print("❌ Error en el reconocimiento de voz.")

    return ""

def speaker(text):
    """Convierte texto en voz y lo reproduce."""

    url = "http://localhost:9020/v1/"

    crear = requests.request("POST", url+"audio", json={"Nombre":"@Test@","Texto":text}, headers={"Content-Type":"application/json"})
    reproducir = requests.request("POST", url+"play2", json={"text":text}, headers={"Content-Type":"application/json"})

def openai_function(question):
    """Envía una pregunta a OpenAI y devuelve la respuesta hablada."""
    sendStatusFace("d")

    try:
        url = "https://n8n.srv792542.hstgr.cloud/webhook/rag-preguntar"

        payload = {"pregunta": question}
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.request("POST", url, json=payload, headers=headers)
        response_c = response.json()["output"]

        print(f"🤖 Respuesta: {response_c}")
        speaker(response_c)
        return response_c
              
    except Exception as e:
        print(f"❌ Error en RAG-n8n: {e}")
        return "Lo siento, hubo un error al procesar tu solicitud."

def stop_listening_after_delay(delay):
    """Detiene la escucha después de un tiempo de inactividad."""
    global listening
    time.sleep(delay)
    with lock:
        listening = False
        print("⏳ Se ha detenido la escucha por inactividad.")

def assistant_interaction():
    """Activa la interacción con OpenAI tras detectar la wake word."""
    global listening
    with lock:
        if not listening:
            listening = True
            threading.Thread(target=stop_listening_after_delay, args=(60,), daemon=True).start()

    speech = recognize_from_microphone()
    print("Speach:", speech)
    if speech:
        openai_function(speech)

def wake_word_listener():
    """Mantiene activo el reconocimiento de la wake word en un bucle infinito."""
    global wake_word_active

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)
    model = speechsdk.KeywordRecognitionModel(MODEL_PATH)

    def recognized_cb(evt):
        """Callback cuando se detecta la wake word."""
        global wake_word_active
        if evt.result.reason == speechsdk.ResultReason.RecognizedKeyword and wake_word_active:
            print(f"🎙️ ¡Wake Word detectada!: {evt.result.text}")
            assistant_interaction()

    def stop_cb(evt):
        """Callback que reinicia el reconocimiento tras un evento de detención."""
        print(f"[INFO] Reiniciando escucha... ({evt})")
        if wake_word_active:
            recognizer.start_keyword_recognition(model)

    # Conectar eventos
    recognizer.recognized.connect(recognized_cb)
    recognizer.session_stopped.connect(stop_cb)
    recognizer.canceled.connect(stop_cb)

    # Iniciar reconocimiento continuo
    print(f"🟢 Sistema activo, esperando la palabra clave '{WAKE_WORD}'...")
    recognizer.start_keyword_recognition(model)

    while True:
        time.sleep(0.5)  # Mantiene el hilo sin consumir demasiada CPU

if __name__ == "__main__":
    # Iniciar la detección de la wake word en un hilo separado
    listener_thread = threading.Thread(target=wake_word_listener, daemon=True)
    listener_thread.start()

    while True:
        time.sleep(1)  # Mantiene el script corriendo sin bloquear el hilo
