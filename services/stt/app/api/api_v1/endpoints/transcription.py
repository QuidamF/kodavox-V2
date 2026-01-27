import shutil
import tempfile
import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import get_transcriber
from app.services.transcriber import TranscriberService
from app.schemas.transcription import TranscriptionResponse

router = APIRouter()

@router.post("/transcribe", response_model=TranscriptionResponse, summary="Transcribe audio file")
async def transcribe_audio_file(
    audio_file: UploadFile = File(...),
    transcriber: TranscriberService = Depends(get_transcriber)
):
    """
    Upload an audio file and return its transcription.
    
    - **audio_file**: The audio file to transcribe (formats supported by FFMPEG).
    """
    temp_dir = tempfile.mkdtemp()
    temp_audio_path = os.path.join(temp_dir, audio_file.filename or "temp_audio")
    
    try:
        # Save uploaded file
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # Transcribe (non-blocking)
        transcription_text = await transcriber.transcribe_file(temp_audio_path)
        
        return TranscriptionResponse(transcription=transcription_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
