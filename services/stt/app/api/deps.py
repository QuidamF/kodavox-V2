from app.services.transcriber import get_transcriber_service, TranscriberService

def get_transcriber() -> TranscriberService:
    return get_transcriber_service()
