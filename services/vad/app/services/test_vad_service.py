import pytest
import asyncio
from vad_service import SileroVADService

# --- Helpers simulados para la prueba ---
def load_wav(filepath: str) -> bytes:
    """Simula la carga de un archivo WAV retornando bytes de prueba."""
    # En un entorno real usaríamos wave o soundfile para cargar el audio
    return b"\x00" * 4096  # Dummy audio data

def chunk_audio(audio_data: bytes, chunk_size: int = 512):
    """Generador que divide el audio en chunks."""
    for i in range(0, len(audio_data), chunk_size):
        yield audio_data[i:i+chunk_size]

# --- Pruebas Unitarias ---

@pytest.mark.asyncio
async def test_vad_detects_speech(monkeypatch):
    """Prueba que el VAD emita speech_start y speech_end correctamente."""
    
    # 1. Configuramos el mock para simular la detección de voz
    # Simulamos que los primeros 3 chunks no tienen voz, los siguientes 4 sí, y luego ya no.
    mock_responses = [False, False, False, True, True, True, True, False, False]
    call_count = 0
    
    def mock_vad_call(self, audio_chunk):
        nonlocal call_count
        result = mock_responses[call_count] if call_count < len(mock_responses) else False
        call_count += 1
        return result

    # Aplicamos el mock al VoiceActivityDetector
    monkeypatch.setattr("vad_service.VoiceActivityDetector.__call__", mock_vad_call)

    # 2. Inicializamos el servicio
    vad = SileroVADService()
    
    # 3. Procesamos audio falso
    fake_audio = load_wav("speech_sample.wav")
    
    events = []
    # chunk_audio generará varios chunks de 512 bytes
    for chunk in chunk_audio(fake_audio, chunk_size=512):
        events += await vad.process_chunk(chunk)

    # 4. Verificamos los eventos emitidos
    # Debería haber exactamente 1 speech_start, 4 speech_frame y 1 speech_end
    start_events = [e for e in events if e["type"] == "speech_start"]
    frame_events = [e for e in events if e["type"] == "speech_frame"]
    end_events = [e for e in events if e["type"] == "speech_end"]
    
    assert len(start_events) == 1, "Debería emitirse exactamente un evento speech_start"
    assert len(frame_events) == 4, "Deberían emitirse eventos speech_frame mientras haya voz"
    assert len(end_events) == 1, "Debería emitirse exactamente un evento speech_end al terminar la voz"

@pytest.mark.asyncio
async def test_vad_no_speech(monkeypatch):
    """Prueba que el VAD no emita nada si hay puro silencio."""
    
    def mock_vad_call(self, audio_chunk):
        return False  # Siempre silencio

    monkeypatch.setattr("vad_service.VoiceActivityDetector.__call__", mock_vad_call)

    vad = SileroVADService()
    fake_audio = load_wav("silence_sample.wav")
    
    events = []
    for chunk in chunk_audio(fake_audio, chunk_size=512):
        events += await vad.process_chunk(chunk)

    assert len(events) == 0, "No debería emitirse ningún evento en silencio absoluto"
