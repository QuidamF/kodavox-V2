from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.api_v1.api import api_router
from app.services.transcriber import get_transcriber_service, update_transcriber_config
from app.database import init_db, get_config, update_config
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Offline Speech-to-Text Microservice using Faster-Whisper",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    print("Initializing STT database...")
    init_db()
    print("Initializing Transcriber Service...")
    # Pre-load model on startup
    get_transcriber_service()
    print("Transcriber Service initialized.")

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

class ConfigUpdate(BaseModel):
    language: Optional[str] = None
    beam_size: Optional[int] = None

@app.get("/api/config")
async def get_config_endpoint():
    """Get current STT configuration."""
    return get_config()

@app.post("/api/config")
async def update_config_endpoint(config: ConfigUpdate):
    """Update STT configuration."""
    data = config.dict(exclude_unset=True)
    update_config(data)
    update_transcriber_config(data)
    return {"status": "updated", "config": get_config()}
