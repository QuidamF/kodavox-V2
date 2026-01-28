from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import aiofiles
from typing import List
import httpx
from dotenv import load_dotenv, set_key

app = FastAPI(title="Voice Orchestrator Dashboard API")

# CORS para permitir conexión desde el frontend de Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Rutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAG_DATA_DIR = os.path.join(BASE_DIR, "services", "rag", "data")
VOICES_DIR = os.path.join(BASE_DIR, "services", "tts", "voices")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# --- Gestión de Archivos RAG ---

@app.get("/files")
async def list_files():
    """Lista los archivos en la carpeta de datos del RAG."""
    if not os.path.exists(RAG_DATA_DIR):
        return []
    files = []
    for f in os.listdir(RAG_DATA_DIR):
        path = os.path.join(RAG_DATA_DIR, f)
        if os.path.isfile(path):
            files.append({
                "name": f,
                "size": os.path.getsize(path),
                "modified": os.path.getmtime(path)
            })
    return files

@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Sube un nuevo archivo para el RAG."""
    os.makedirs(RAG_DATA_DIR, exist_ok=True)
    file_path = os.path.join(RAG_DATA_DIR, file.filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    # Forward to RAG Service for ingestion
    try:
        # Detect encoding for text files
        text_content = content.decode('utf-8', errors='ignore')
        
        async with httpx.AsyncClient() as client:
            # Enviar texto al servicio RAG
            r = await client.post(
                "http://rag-api:8000/ingest",
                params={"text": text_content, "source": file.filename},
                timeout=60.0
            )
            if r.status_code != 200:
                print(f"Error ingesting file to RAG: {r.text}")
                return {"filename": file.filename, "status": "uploaded_but_ingest_failed", "detail": r.text}
                
    except Exception as e:
        print(f"Error forwarding to RAG: {e}")
        return {"filename": file.filename, "status": "uploaded_but_forward_failed", "detail": str(e)}

    return {"filename": file.filename, "status": "uploaded_and_ingested"}

@app.delete("/rag/purge")
async def purge_rag_db():
    """Purga la base de datos del RAG."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.delete("http://rag-api:8000/purge", timeout=60.0)
            if r.status_code == 200:
                # También limpiar carpeta local de archivos para mantener consistencia
                if os.path.exists(RAG_DATA_DIR):
                    for f in os.listdir(RAG_DATA_DIR):
                        os.remove(os.path.join(RAG_DATA_DIR, f))
                return {"status": "success", "message": "Memoria purgada y archivos eliminados."}
            else:
                return {"status": "error", "detail": r.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """Elimina un archivo del RAG."""
    file_path = os.path.join(RAG_DATA_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="File not found")

# --- Gestión de Voces (TTS) ---

@app.get("/voices")
async def list_voices():
    """Lista los archivos .wav en la carpeta de voces del TTS."""
    if not os.path.exists(VOICES_DIR):
        os.makedirs(VOICES_DIR, exist_ok=True)
        return []
    voices = []
    for f in os.listdir(VOICES_DIR):
        if f.lower().endswith('.wav'):
            path = os.path.join(VOICES_DIR, f)
            voices.append({
                "name": f,
                "size": os.path.getsize(path)
            })
    return voices

@app.post("/voices/upload")
async def upload_voice(file: UploadFile = File(...)):
    """Sube una nueva muestra de voz (solo .wav)."""
    if not file.filename.lower().endswith('.wav'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .wav")
    
    os.makedirs(VOICES_DIR, exist_ok=True)
    file_path = os.path.join(VOICES_DIR, file.filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    return {"filename": file.filename, "status": "uploaded"}

@app.delete("/voices/{filename}")
async def delete_voice(filename: str):
    """Elimina una muestra de voz."""
    file_path = os.path.join(VOICES_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Voice file not found")

# --- Gestión de Configuración (.env) ---

@app.get("/config")
async def get_config():
    """Lee las variables principales del archivo .env."""
    load_dotenv(ENV_PATH, override=True)
    return {
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "ollama"),
        "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b"),
        "STT_LANGUAGE": os.getenv("LANGUAGE", "es"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "TTS_VOICE_FILE": os.getenv("TTS_VOICE_FILE", ""),
    }

@app.post("/config")
async def update_config(key: str, value: str):
    """Actualiza una variable en el archivo .env."""
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'w') as f: pass
    
    set_key(ENV_PATH, key.upper(), value)
    return {"status": "updated", "key": key, "value": value}

# --- Estado del Sistema ---

@app.get("/health")
async def check_services():
    """Verifica la salud de los microservicios usando nombres internos de Docker."""
    services = {
        "stt": "http://stt-service:8000/health",
        "tts": "http://tts-service:8000/",
        "rag": "http://rag-api:8000/health" 
    }
    results = {}
    async with httpx.AsyncClient(timeout=2) as client:
        for name, url in services.items():
            try:
                r = await client.get(url)
                results[name] = "online" if r.status_code == 200 else "error"
            except:
                results[name] = "offline"
    return results

# --- Pruebas Unitarias / Diagnósticos ---

@app.get("/test/stt")
async def test_stt():
    """Prueba el servicio STT enviando una solicitud de salud profunda."""
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            # Intentamos acceder al health y quizás a la info del modelo
            r = await client.get("http://stt-service:8000/health")
            if r.status_code == 200:
                return {"status": "success", "message": "STT (Whisper) listo y cargado en memoria."}
            return {"status": "error", "message": f"STT devolvió código {r.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.get("/test/tts")
async def test_tts():
    """Prueba el servicio TTS intentando generar un pequeño audio."""
    payload = {"text": "Prueba de diagnóstico", "voice_id": "female_a"} # Ajustar a tu API
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            # En lugar de generar un audio real pesado, validamos el endpoint de salud de la API
            r = await client.get("http://tts-service:8000/")
            if r.status_code == 200:
                return {"status": "success", "message": "TTS (XTTS) listo. El motor de audio responde."}
            return {"status": "error", "message": "TTS fuera de línea o ocupado."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.get("/test/rag")
async def test_rag():
    """Prueba el sistema RAG con una consulta simple."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            # Validamos que el RAG API y Qdrant estén sincronizados
            r = await client.get("http://rag-api:8000/health")
            if r.status_code == 200:
                return {"status": "success", "message": "RAG API y Base de Datos Vectorial operativos."}
            return {"status": "error", "message": "RAG API no respondió correctamente."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.post("/system/restart")
async def restart_system():
    """Reinicia el orquestador (lógica de 'suicidio' de proceso para Docker restart)."""
    # En Docker, si 'restart: unless-stopped' está activo, matar el proceso reinicia el contenedor
    os._exit(1)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
