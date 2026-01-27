import json
import tempfile
import os
import shutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from app.api.deps import get_transcriber
from app.services.transcriber import TranscriberService

router = APIRouter()

@router.websocket("/streaming")
async def websocket_transcription(
    websocket: WebSocket,
    transcriber: TranscriberService = Depends(get_transcriber)
):
    """
    WebSocket endpoint for real-time transcription.
    Expects binary audio data or JSON control messages.
    """
    await websocket.accept()
    
    audio_buffer = bytearray()
    temp_dir = tempfile.mkdtemp()
    
    try:
        while True:
            data = await websocket.receive()
            
            if "bytes" in data:
                audio_buffer.extend(data["bytes"])
            
            elif "text" in data:
                try:
                    message = json.loads(data["text"])
                except json.JSONDecodeError:
                    continue

                if message.get("action") == "stop":
                    if not audio_buffer:
                        await websocket.send_text(json.dumps({"transcript": "", "message": "No audio received."}))
                        # Continue or break depending on requirement. Here we'll clear buffer and wait for more.
                        # If the intention is to close connection after one transcription, use break.
                        # For now, let's allow multiple transcriptions in one session.
                    else:
                        # Save buffer to file
                        temp_audio_path = os.path.join(temp_dir, "stream.audio")
                        with open(temp_audio_path, 'wb') as f:
                            f.write(audio_buffer)
                        
                        # Transcribe
                        try:
                            # Note: In a real streaming scenario, we might want to transcribe chunks.
                            # Here we follow the existing logic of transcribing the whole buffer on "stop".
                            transcription = await transcriber.transcribe_file(temp_audio_path)
                            response = {"transcript": transcription}
                            await websocket.send_text(json.dumps(response))
                        except Exception as e:
                            await websocket.send_text(json.dumps({"error": str(e)}))
                        
                        # Reset buffer
                        audio_buffer.clear()

    except WebSocketDisconnect:
        pass # Client disconnected normally
    except Exception as e:
        # Try to send error if connection is still open
        if websocket.client_state.name != 'DISCONNECTED':
             await websocket.send_text(json.dumps({"error": str(e)}))
            
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
