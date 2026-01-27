from pydantic import BaseModel

class TranscriptionResponse(BaseModel):
    transcription: str
    language: str | None = None
    language_probability: float | None = None
