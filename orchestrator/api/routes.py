import os
import json
import zipfile
import tempfile
import shutil
import asyncio
import sys
import httpx
from fastapi import APIRouter, UploadFile, File, Form, Body, HTTPException
from fastapi.responses import FileResponse
from services.usage_tracker import tracker
from core.config import TTS_PROVIDER

router = APIRouter()

# --- Rutas Credenciales Seguras ---

@router.get("/api/config/credentials/status")
async def get_credentials_status():
    from main import pipeline
    from core.config import TTS_PROVIDER
    return {
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
        "ELEVENLABS_API_KEY": bool(os.getenv("ELEVENLABS_API_KEY")),
        "llm_provider": getattr(pipeline, 'llm_provider_name', os.getenv('LLM_PROVIDER', 'ollama')),
        "stt_provider": getattr(pipeline, 'stt_provider', os.getenv('STT_PROVIDER', 'whisper')),
        "tts_provider": TTS_PROVIDER
    }

@router.post("/api/config/credentials")
async def update_credentials(payload: dict = Body(...)):
    from api.credentials import save_credentials
    save_credentials(payload)
    # Al cambiar llaves maestras, reiniciamos el motor para que todos los servicios las tomen
    asyncio.create_task(restart_server_task())
    return {"message": "Credenciales guardadas exitosamente", "needs_restart": True}

# --- Rutas RAG ---

@router.get("/api/rag/collections")
async def get_collections():
    from main import pipeline
    if pipeline.rag_service is None:
        from services.rag_chroma import ChromaRAGService
        pipeline.rag_service = ChromaRAGService()
    collections = pipeline.rag_service.list_collections()
    return {"collections": collections, "active": pipeline.active_rag_collection}

@router.post("/api/rag/collections")
async def create_collection(name: str = Body(..., embed=True)):
    from main import pipeline
    if pipeline.rag_service is None:
        from services.rag_chroma import ChromaRAGService
        pipeline.rag_service = ChromaRAGService()
    pipeline.rag_service.create_collection(name)
    return {"message": f"Colección '{name}' creada o ya existente."}

@router.delete("/api/rag/collections/{name}")
async def delete_collection(name: str):
    from main import pipeline
    if pipeline.rag_service is None:
        from services.rag_chroma import ChromaRAGService
        pipeline.rag_service = ChromaRAGService()
    pipeline.rag_service.delete_collection(name)
    if pipeline.active_rag_collection == name:
        pipeline.active_rag_collection = ""
        pipeline._save_engine_state()
    return {"message": f"Colección '{name}' eliminada."}

@router.post("/api/rag/active")
async def set_active_collection(name: str = Body(..., embed=True)):
    from main import pipeline
    pipeline.active_rag_collection = name if name.lower() != "none" else ""
    pipeline._save_engine_state()
    return {"message": f"Colección activa cambiada a '{pipeline.active_rag_collection}'"}

@router.post("/api/rag/upload")
async def upload_document(collection: str = Form(...), file: UploadFile = File(...)):
    from main import pipeline
    if pipeline.rag_service is None:
        from services.rag_chroma import ChromaRAGService
        pipeline.rag_service = ChromaRAGService()
    try:
        content = await file.read()
        pipeline.rag_service.add_document(collection, file.filename, content)
        return {"message": f"Archivo '{file.filename}' indexado correctamente en '{collection}'."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Rutas Personalidad y Voces ---

@router.get("/api/config/personality")
async def get_personality():
    from main import pipeline
    return {
        "personality_prompt": pipeline.personality_prompt,
        "llm_temperature": getattr(pipeline, 'llm_temperature', 0.7),
        "rag_strict_mode": getattr(pipeline, 'rag_strict_mode', False)
    }

@router.post("/api/config/personality")
async def set_personality(payload: dict = Body(...)):
    from main import pipeline
    if "personality_prompt" in payload:
        pipeline.personality_prompt = payload["personality_prompt"]
    if "llm_temperature" in payload:
        pipeline.llm_temperature = float(payload["llm_temperature"])
    if "rag_strict_mode" in payload:
        pipeline.rag_strict_mode = bool(payload["rag_strict_mode"])
        
    pipeline._save_engine_state()
    return {"message": "Configuración de personalidad actualizada"}

@router.post("/api/config/voices/clone")
async def clone_voice(name: str = Form(...), file: UploadFile = File(...)):
    from main import pipeline
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de ElevenLabs no configurada")
        
    url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {"xi-api-key": api_key, "Accept": "application/json"}
    file_content = await file.read()
    files = [("files", (file.filename, file_content, file.content_type))]
    data = {"name": name, "description": "Clonado desde KodaVox Dashboard"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data, files=files, timeout=60.0)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Error al clonar en ElevenLabs")
            result = response.json()
            new_voice_id = result.get("voice_id")
            if new_voice_id:
                pipeline.elevenlabs_voices.append({"name": name, "id": new_voice_id})
                pipeline._save_engine_state()
                return {"message": f"Voz '{name}' clonada exitosamente", "voice_id": new_voice_id}
            else:
                raise HTTPException(status_code=500, detail="No se recibió un ID de voz")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/config/voices")
async def get_voices():
    from main import pipeline
    return {
        "voices": pipeline.elevenlabs_voices,
        "active_voice_id": pipeline.active_voice_id,
        "settings": {
            "stability": getattr(pipeline, 'voice_stability', 0.5),
            "similarity_boost": getattr(pipeline, 'voice_similarity_boost', 0.75),
            "style": getattr(pipeline, 'voice_style', 0.0),
            "use_speaker_boost": getattr(pipeline, 'voice_use_speaker_boost', True)
        }
    }

@router.post("/api/config/voices")
async def add_voice(name: str = Body(...), id: str = Body(...)):
    from main import pipeline
    if any(v["id"] == id for v in pipeline.elevenlabs_voices):
        raise HTTPException(status_code=400, detail="La voz con este ID ya existe")
    pipeline.elevenlabs_voices.append({"name": name, "id": id})
    pipeline._save_engine_state()
    return {"message": f"Voz '{name}' agregada"}

@router.delete("/api/config/voices/{voice_id}")
async def delete_voice(voice_id: str):
    from main import pipeline
    pipeline.elevenlabs_voices = [v for v in pipeline.elevenlabs_voices if v["id"] != voice_id]
    pipeline._save_engine_state()
    return {"message": "Voz eliminada"}

@router.post("/api/config/voices/active")
async def set_active_voice(payload: dict = Body(...)):
    from main import pipeline
    voice_id = payload.get("id")
    if not any(v["id"] == voice_id for v in pipeline.elevenlabs_voices):
        raise HTTPException(status_code=400, detail="Voice ID no registrado")
        
    pipeline.active_voice_id = voice_id
    if getattr(pipeline, 'elevenlabs_tts', None) is not None:
        from services.elevenlabs_tts import ElevenLabsTTSService
        pipeline.elevenlabs_tts = ElevenLabsTTSService(voice_id=voice_id)
        pipeline._update_elevenlabs_settings()
        
    pipeline._save_engine_state()
    return {"message": "Voz activa actualizada"}

@router.post("/api/config/voices/settings")
async def update_voice_settings(payload: dict = Body(...)):
    from main import pipeline
    pipeline.voice_stability = float(payload.get("stability", getattr(pipeline, 'voice_stability', 0.5)))
    pipeline.voice_similarity_boost = float(payload.get("similarity_boost", getattr(pipeline, 'voice_similarity_boost', 0.75)))
    pipeline.voice_style = float(payload.get("style", getattr(pipeline, 'voice_style', 0.0)))
    pipeline.voice_use_speaker_boost = bool(payload.get("use_speaker_boost", getattr(pipeline, 'voice_use_speaker_boost', True)))
    
    pipeline._update_elevenlabs_settings()
    pipeline._save_engine_state()
    return {"message": "Voice settings updated successfully"}

@router.get("/api/config/wakeword")
async def get_wakeword():
    from main import pipeline
    return {
        "wake_word": pipeline.wake_word,
        "wake_session_timeout": pipeline.wake_session_timeout,
        "vad_threshold": getattr(pipeline, 'vad_threshold', 0.6),
        "vad_end_silence_seconds": getattr(pipeline, 'vad_end_silence_seconds', 0.7),
        "stt_min_speech_seconds": getattr(pipeline, 'stt_min_speech_seconds', 0.3),
        "vad_pre_padding_seconds": getattr(pipeline, 'vad_pre_padding_seconds', 0.2),
        "tts_provider": TTS_PROVIDER,
        "stt_provider": pipeline.stt_provider,
        "piper_length_scale": getattr(pipeline, 'piper_length_scale', 0.85),
        "piper_noise_scale": getattr(pipeline, 'piper_noise_scale', 0.75)
    }

@router.post("/api/config/wakeword")
async def set_wakeword(payload: dict = Body(...)):
    from main import pipeline
    if "word" in payload and payload["word"] is not None:
        pipeline.wake_word = payload["word"]
    if "timeout" in payload and payload["timeout"] is not None:
        pipeline.wake_session_timeout = int(payload["timeout"])
    if "vad_threshold" in payload:
        pipeline.vad_threshold = float(payload["vad_threshold"])
    if "vad_end_silence_seconds" in payload:
        pipeline.vad_end_silence_seconds = float(payload["vad_end_silence_seconds"])
    if "stt_min_speech_seconds" in payload:
        pipeline.stt_min_speech_seconds = float(payload["stt_min_speech_seconds"])
    if "vad_pre_padding_seconds" in payload:
        pipeline.vad_pre_padding_seconds = float(payload["vad_pre_padding_seconds"])
    if "piper_length_scale" in payload:
        pipeline.piper_length_scale = float(payload["piper_length_scale"])
    if "piper_noise_scale" in payload:
        pipeline.piper_noise_scale = float(payload["piper_noise_scale"])

    pipeline._save_engine_state()
    return {"message": "Configuración actualizada exitosamente"}

@router.get("/api/config/hardware")
async def get_hardware():
    from main import pipeline
    return {
        "native_audio_output": getattr(pipeline, 'native_audio_output', True),
        "robot_face_sync": getattr(pipeline, 'robot_face_sync', False),
        "enabled": getattr(pipeline, 'enabled', True),
        "cost_rates": getattr(pipeline, 'cost_rates', {"openai": 0.15, "gemini": 0.0, "elevenlabs": 15.0})
    }

@router.post("/api/config/hardware")
async def set_hardware(payload: dict = Body(...)):
    from main import pipeline
    if "native_audio_output" in payload:
        pipeline.native_audio_output = payload["native_audio_output"]
    if "robot_face_sync" in payload:
        pipeline.robot_face_sync = payload["robot_face_sync"]
    if "enabled" in payload:
        pipeline.enabled = bool(payload["enabled"])
        if not pipeline.enabled:
            asyncio.create_task(pipeline._set_engine_state("disabled"))
        else:
            asyncio.create_task(pipeline._set_engine_state("idle"))
    if "cost_rates" in payload:
        pipeline.cost_rates = payload["cost_rates"]
        
    pipeline._save_engine_state()
    return {"message": "Configuración actualizada exitosamente"}

@router.post("/api/engine/toggle")
async def toggle_engine(payload: dict = Body(...)):
    from main import pipeline
    if "enabled" in payload:
        pipeline.enabled = bool(payload["enabled"])
        pipeline._save_engine_state()
        state_str = "activado" if pipeline.enabled else "desactivado (muted)"
        if not pipeline.enabled:
            asyncio.create_task(pipeline._set_engine_state("disabled"))
        else:
            asyncio.create_task(pipeline._set_engine_state("idle"))
        return {"enabled": pipeline.enabled, "message": f"KodaVox {state_str}"}
    return {"enabled": getattr(pipeline, 'enabled', True)}

@router.post("/api/tts/test")
async def test_tts(payload: dict = Body(...)):
    from main import pipeline
    text = payload.get("text", "Hola, esta es una prueba de voz de KodaVox.")
    if TTS_PROVIDER == "off":
        raise HTTPException(status_code=400, detail="El proveedor TTS está desactivado (off).")
    asyncio.create_task(pipeline.play_tts(text))
    return {"message": "Sintetizando voz..."}

@router.get("/api/diagnostics/health")
async def get_health():
    from main import pipeline
    mic_active = False
    try:
        if hasattr(pipeline, 'stream') and pipeline.stream is not None:
            mic_active = bool(pipeline.stream.is_active())
        elif hasattr(pipeline, 'pa') and pipeline.pa is not None:
            mic_active = True
    except Exception:
        mic_active = False

    return {
        "vad": pipeline.vad_model is not None,
        "stt": pipeline.stt_model is not None or pipeline.elevenlabs_stt is not None,
        "stt_provider": pipeline.stt_provider,
        "llm": pipeline.llm_provider is not None,
        "rag": pipeline.rag_service is not None,
        "microphone_active": mic_active,
        "is_speaking": pipeline.is_speaking,
        "is_processing": pipeline.is_processing
    }

@router.get("/api/diagnostics/usage")
async def get_usage():
    return tracker.get_all_stats()

@router.get("/api/diagnostics/providers")
async def get_providers_status():
    from main import pipeline
    from core.config import TTS_PROVIDER
    
    active_llm = getattr(pipeline, 'llm_provider_name', os.getenv('LLM_PROVIDER', 'ollama'))
    active_stt = getattr(pipeline, 'stt_provider', os.getenv('STT_PROVIDER', 'whisper'))
    active_tts = TTS_PROVIDER

    status = {
        "elevenlabs": {"status": "inactive", "details": None},
        "openai": {"status": "inactive"},
        "gemini": {"status": "inactive"}
    }
    
    el_key = os.getenv("ELEVENLABS_API_KEY")
    oa_key = os.getenv("OPENAI_API_KEY")
    gem_key = os.getenv("GEMINI_API_KEY")

    if active_stt == 'elevenlabs' or active_tts == 'elevenlabs':
        if el_key:
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(
                        "https://api.elevenlabs.io/v1/models",
                        headers={"xi-api-key": el_key},
                        timeout=15.0
                    )
                    if res.status_code == 200:
                        status["elevenlabs"] = {
                            "status": "ok",
                            "status_tier": "API Key Válida"
                        }
                    elif res.status_code == 401:
                        try:
                            error_data = res.json()
                            detail = error_data.get("detail", {})
                            if isinstance(detail, dict):
                                status_str = str(detail.get("status", "")).lower()
                            else:
                                status_str = str(detail).lower()

                            if "invalid" in status_str:
                                status["elevenlabs"] = {"status": "invalid_key", "code": 401}
                            else:
                                status["elevenlabs"] = {"status": "ok", "status_tier": "API Key Válida (Scoped)"}
                        except Exception:
                            status["elevenlabs"] = {"status": "invalid_key", "code": 401}
                    else:
                        status["elevenlabs"] = {"status": "error", "code": res.status_code}
            except Exception as e:
                status["elevenlabs"] = {"status": "error", "message": str(e)}
        else:
            status["elevenlabs"] = {"status": "missing_key"}

    if active_llm == 'openai':
        if oa_key:
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {oa_key}"},
                        timeout=15.0
                    )
                    status["openai"] = {"status": "ok" if res.status_code == 200 else f"error_{res.status_code}"}
            except Exception as e:
                status["openai"] = {"status": "error", "message": str(e)}
        else:
            status["openai"] = {"status": "missing_key"}

    if active_llm == 'gemini':
        if gem_key:
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(
                        f"https://generativelanguage.googleapis.com/v1beta/models?key={gem_key}",
                        timeout=15.0
                    )
                    status["gemini"] = {"status": "ok" if res.status_code == 200 else f"error_{res.status_code}"}
            except Exception as e:
                status["gemini"] = {"status": "error", "message": str(e)}
        else:
            status["gemini"] = {"status": "missing_key"}
        
    return status

@router.post("/api/config/export")
async def export_config(payload: dict = Body(...)):
    include_env = payload.get("include_env", False)
    include_rag = payload.get("include_rag", False)
    include_credentials = payload.get("include_credentials", True)
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    state_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "engine_state.json")
    env_path = os.path.join(project_root, ".env")
    creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "credentials.json")
    chroma_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")
    
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "kodavox_full_profile.zip")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            manifest = {
                "has_state": True,
                "has_env": include_env,
                "has_rag": include_rag,
                "has_credentials": include_credentials and os.path.exists(creds_path),
                "version": "2.0"
            }
            zipf.writestr("manifest.json", json.dumps(manifest))
            if os.path.exists(state_path):
                zipf.write(state_path, "engine_state.json")
            if include_env and os.path.exists(env_path):
                zipf.write(env_path, ".env")
            if include_credentials and os.path.exists(creds_path):
                zipf.write(creds_path, "credentials.json")
            if include_rag and os.path.exists(chroma_path):
                for root, _, files in os.walk(chroma_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join("chroma_db", os.path.relpath(file_path, chroma_path))
                        zipf.write(file_path, arcname)
                        
        return FileResponse(path=zip_path, filename="kodavox_full_profile.zip", media_type="application/zip")
    except Exception as e:
        print(f"[Error Export] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting profile: {str(e)}")

async def restart_server_task():
    await asyncio.sleep(2)
    os.execv(sys.executable, ['python'] + sys.argv)

@router.post("/api/config/import")
async def import_config(file: UploadFile = File(...)):
    from main import pipeline
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un ZIP (.zip)")
        
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "uploaded.zip")
    
    try:
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_dir)
            
        manifest_path = os.path.join(extract_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            raise HTTPException(status_code=400, detail="El archivo no es un perfil de KodaVox válido (falta manifest.json)")
            
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        needs_restart = False
        
        if manifest.get("has_state"):
            state_src = os.path.join(extract_dir, "engine_state.json")
            state_dest = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "engine_state.json")
            if os.path.exists(state_src):
                shutil.copy2(state_src, state_dest)
                pipeline._load_engine_state()
                if TTS_PROVIDER == "elevenlabs" and getattr(pipeline, 'active_voice_id', None):
                    from services.elevenlabs_tts import ElevenLabsTTSService
                    pipeline.elevenlabs_tts = ElevenLabsTTSService(voice_id=pipeline.active_voice_id)
                    pipeline._update_elevenlabs_settings()
                    
        if manifest.get("has_env"):
            env_src = os.path.join(extract_dir, ".env")
            env_dest = os.path.join(project_root, ".env")
            if os.path.exists(env_src):
                shutil.copy2(env_src, env_dest)
                needs_restart = True

        if manifest.get("has_credentials"):
            creds_src = os.path.join(extract_dir, "credentials.json")
            creds_dest = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "credentials.json")
            if os.path.exists(creds_src):
                os.makedirs(os.path.dirname(creds_dest), exist_ok=True)
                shutil.copy2(creds_src, creds_dest)
                needs_restart = True
                
        if manifest.get("has_rag"):
            chroma_src = os.path.join(extract_dir, "chroma_db")
            chroma_dest = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")
            if os.path.exists(chroma_src):
                if os.path.exists(chroma_dest):
                    shutil.rmtree(chroma_dest)
                shutil.copytree(chroma_src, chroma_dest)
                needs_restart = True
                
        if needs_restart:
            asyncio.create_task(restart_server_task())
            
        return {"message": "Perfil importado exitosamente", "needs_restart": needs_restart}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al importar configuración: {e}")
