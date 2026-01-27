from fastapi import APIRouter
from app.api.api_v1.endpoints import transcription, websocket

api_router = APIRouter()
api_router.include_router(transcription.router, tags=["transcription"])
# WebSocket router can be included directly or mounted separately.
# Since APIRouter supports websocket, we can include it.
api_router.include_router(websocket.router, tags=["websocket"])
