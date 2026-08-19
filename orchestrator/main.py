import os
import sys

# Hack para que los imports "from main import pipeline" de routes.py usen la misma instancia de la pipeline corriendo
sys.modules['main'] = sys.modules[__name__]

import asyncio
import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.credentials import load_credentials
load_credentials()

from core.pipeline import EnginePipeline
from api.routes import router

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
pipeline = EnginePipeline(sio=sio)

@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline.loop = asyncio.get_running_loop()
    await pipeline.setup_tts()
    pipeline.run()
    yield
    if hasattr(pipeline, 'stream'):
        pipeline.stream.stop_stream()
        pipeline.stream.close()
    pipeline.pa.terminate()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    engine_port = int(os.getenv("ENGINE_PORT", "5000"))
    uvicorn.run(socket_app, host="0.0.0.0", port=engine_port, log_level="warning")
