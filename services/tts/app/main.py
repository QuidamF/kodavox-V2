import os
import torch
import torchaudio
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager, contextmanager
import asyncio
import numpy as np
import json
# Removed pydub and tempfile as we now enforce wav inputs

# New imports for the correct XTTSv2 implementation
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
from huggingface_hub import snapshot_download

# --- Local Imports ---
from .text_processing import split_into_sentences

# --- Constants ---
VOICES_DIR = "voices"
OUTPUT_DIR = "audio_outputs"
os.makedirs(VOICES_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# --- Device Setup ---
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"--- TTS starting on {device} ---")
print("--- VERSION CHECK: STABLE RESET v1.0 (Commas + 140 chars) ---")


# --- TTS Model Loading ---
tts_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tts_model
    print("--- Downloading and loading XTTSv2 model ---")
    try:
        checkpoint_dir = snapshot_download("coqui/XTTS-v2")
        config_path = os.path.join(checkpoint_dir, "config.json")
        
        config = XttsConfig()
        config.load_json(config_path)
        
        tts_model = Xtts.init_from_config(config)
        tts_model.load_checkpoint(config, checkpoint_dir=checkpoint_dir, use_deepspeed=False)
        tts_model.to(device)
        print("--- XTTSv2 model loaded successfully ---")
    except Exception as e:
        print(f"--- FATAL: Failed to load XTTSv2 model: {e} ---")
        # In a real app, you might want to exit or handle this more gracefully
        tts_model = None
    
    yield
    
    print("--- Cleaning up TTS model ---")
    # No explicit cleanup needed for the model object itself, Python's GC will handle it.


# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)


# --- Service Configuration ---
class ServiceConfig(BaseModel):
    voice_sample: Optional[str] = None
    language: Optional[str] = "es"

CONFIG_FILE = "tts_config.json"

def load_config():
    """Laws config from disk if exists"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return ServiceConfig(**data)
        except Exception as e:
            print(f"--- Error loading config: {e} ---")
    return ServiceConfig()

def save_config(config: ServiceConfig):
    """Saves config to disk"""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config.model_dump(), f, indent=4)
        print("--- Config saved to disk ---")
    except Exception as e:
        print(f"--- Error saving config: {e} ---")

# Global configuration with defaults (loaded from disk)
current_config = load_config()

# --- Request Models ---
class TTSRequest(BaseModel):
    text: str
    voice_sample: Optional[str] = None
    language: Optional[str] = None


# --- Voice Latent Caching ---
# Cache structure: { "voice_filename": (gpt_cond_latent, speaker_embedding) }
speaker_latents_cache = {}

def get_speaker_latents(voice_sample_name: str):
    """
    Retrieves cached speaker latents or computes them if not present.
    Enforces that the voice sample is a .wav file.
    """
    if not voice_sample_name.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Invalid voice sample format. Only .wav files are supported.")
    
    # Check cache first
    if voice_sample_name in speaker_latents_cache:
        print(f"--- Cache HIT for voice: {voice_sample_name} ---")
        return speaker_latents_cache[voice_sample_name]
    
    print(f"--- Cache MISS for voice: {voice_sample_name} ---")
    
    voice_path = os.path.join(VOICES_DIR, voice_sample_name)
    if not os.path.exists(voice_path):
        raise HTTPException(status_code=404, detail=f"Voice sample '{voice_sample_name}' not found in '{VOICES_DIR}'.")
        
    print(f"--- Computing latents for: {voice_path} ---")
    try:
        gpt_cond_latent, speaker_embedding = tts_model.get_conditioning_latents(audio_path=[voice_path])
        # Cache the result
        speaker_latents_cache[voice_sample_name] = (gpt_cond_latent, speaker_embedding)
        return gpt_cond_latent, speaker_embedding
    except Exception as e:
        print(f"--- Error computing latents: {e} ---")
        raise HTTPException(status_code=500, detail=f"Failed to process voice sample: {str(e)}")





# --- API Endpoints ---
@app.get("/")
async def root():
    if tts_model is None:
        raise HTTPException(status_code=503, detail="TTS model is not available.")
    return {"status": "online", "message": "TTS service is running", "config": current_config}


@app.post("/api/config")
async def update_config(config: ServiceConfig):
    """
    Updates the default configuration for the service.
    If a voice_sample is provided, it attempts to pre-compute and cache the latents.
    """
    global current_config
    
    if config.language:
        current_config.language = config.language
        print(f"--- Config: Default language set to {config.language} ---")

    if config.voice_sample:
        print(f"--- Config: Pre-loading voice {config.voice_sample} ---")
        try:
            # Trigger latent computation (this will cache it)
            get_speaker_latents(config.voice_sample)
            current_config.voice_sample = config.voice_sample
            print(f"--- Config: Voice {config.voice_sample} loaded and active ---")
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load voice: {e}")

    # Persist the new configuration
    save_config(current_config)

    return {"status": "updated", "config": current_config}



@app.post("/api/tts/batch")
async def tts_batch(request: TTSRequest):
    if tts_model is None:
        raise HTTPException(status_code=503, detail="TTS model is not available.")
        
    print(f"--- Received batch request: {request} ---")
    
    try:
        # Determine voice and language (Request > Config > Default is handled by logic)
        voice_sample = request.voice_sample or current_config.voice_sample
        language = request.language or current_config.language

        if not voice_sample:
            raise HTTPException(status_code=400, detail="Voice sample not specified in request or default config.")
        if not language:
             language = "es" # Fallback if even config is empty

        # Get latents (cached or computed)
        gpt_cond_latent, speaker_embedding = get_speaker_latents(voice_sample)

        # Split text into chunks to avoid distortion on long texts
        sentences = split_into_sentences(request.text)
        print(f"--- Text split into {len(sentences)} chunks for processing ---")

        generated_wavs = []
        silence_duration = 0.25 # seconds
        silence = torch.zeros(1, int(24000 * silence_duration)) # 24kHz silence

        print("--- Starting batch inference (per chunk) ---")
        for i, sentence in enumerate(sentences):
            if not sentence.strip(): continue
            
            # Ensure punctuation for stability
            if sentence[-1] not in ".,!?;:":
                sentence += ","

            print(f"--- Processing chunk {i+1}/{len(sentences)}: '{sentence[:30]}...' ---")
            
            out = tts_model.inference(
                sentence,
                language,
                gpt_cond_latent,
                speaker_embedding
            )
            # out["wav"] is a list or numpy array, convert to tensor
            wav_tensor = torch.tensor(out["wav"])
            generated_wavs.append(wav_tensor)
            
            # Add silence after each chunk (except the last one)
            if i < len(sentences) - 1:
                generated_wavs.append(silence)
        
        # Concatenate all audio chunks
        if generated_wavs:
            full_wav = torch.cat(generated_wavs, dim=0).unsqueeze(0)
            print(f"--- Batch inference finished. Total audio length: {full_wav.shape[-1]} samples ---")
        else:
            # Handle empty case
            full_wav = torch.zeros(1, 1)

        output_filename = f"{os.path.splitext(voice_sample)[0]}_batch_output.wav"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # XTTS outputs at 24kHz
        torchaudio.save(output_path, full_wav, 24000)
        
        print(f"--- Audio generated at: {output_path} ---")
        return FileResponse(path=output_path, media_type="audio/wav", filename=output_filename)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"--- Error during TTS generation: {e} ---")
        raise HTTPException(status_code=500, detail=f"An error occurred during TTS processing: {str(e)}")


@app.post("/api/tts/stream")
async def tts_stream(request: TTSRequest):
    if tts_model is None:
        raise HTTPException(status_code=503, detail="TTS model is not available.")

    print(f"--- Received stream request: {request} ---")

    async def streaming_generator():
        try:
            # Determine voice and language
            voice_sample = request.voice_sample or current_config.voice_sample
            language = request.language or current_config.language

            if not voice_sample:
                # We can't raise HTTP exception easily inside a generator, so we print and return
                print("--- Error: No voice sample provided for stream ---")
                return

            # Get latents (cached or computed)
            gpt_cond_latent, speaker_embedding = get_speaker_latents(voice_sample)
            
            # Split text into chunks to avoid distortion on long texts
            sentences = split_into_sentences(request.text)
            print(f"--- Stream text split into {len(sentences)} chunks ---")
            
            # Create silence bytes for streaming (24kHz, 16-bit mono)
            # 0.1 seconds * 24000 samples/sec * 2 bytes/sample (Shorter silence for comma flow)
            silence_bytes = b'\x00' * int(24000 * 0.1 * 2)

            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue

                # XTTS is much more stable if text ends with punctuation
                
                # XTTS is much more stable if text ends with punctuation
                # If the chunk was cut abruptly use a comma to induce a short pause/continuation flow.
                if sentence[-1] not in ".,!?;:":
                    sentence += ","

                print(f"--- Streaming chunk {i+1}/{len(sentences)}: '{sentence[:30]}...' ---")
                
                chunks = tts_model.inference_stream(
                    sentence,
                    language or "es",
                    gpt_cond_latent,
                    speaker_embedding
                )
                
                for chunk in chunks:
                    # Convert tensor to bytes
                    # Clamp values to [-1, 1] to prevent clipping/noise
                    chunk_np = chunk.cpu().numpy()
                    chunk_np = np.clip(chunk_np, -1, 1)
                    audio_bytes = (chunk_np * 32767).astype(np.int16).tobytes()
                    yield audio_bytes
                
                # Yield silence between sentences
                if i < len(sentences) - 1:
                    yield silence_bytes

            print("--- Finished streaming audio chunks ---")
        except Exception as e:
            print(f"--- An error occurred during streaming: {e} ---")

    return StreamingResponse(streaming_generator(), media_type="audio/wav")
