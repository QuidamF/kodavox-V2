from fastapi import FastAPI, Query, HTTPException
import os
import asyncio
from functools import lru_cache
from typing import List, Optional, Protocol
import httpx
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel # Import BaseModel

# --- Configuración ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost:6333")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "4"))

# RAG Params Defaults (from env vars)
DEFAULT_K = int(os.getenv("RAG_K", "3"))
DEFAULT_MAX_CONTEXT = int(os.getenv("RAG_MAX_CONTEXT", "4000"))
DEFAULT_TEMPERATURE = float(os.getenv("RAG_TEMPERATURE", "0.0"))
DEFAULT_MAX_LENGTH = int(os.getenv("RAG_MAX_LENGTH", "1024"))

# Other RAG related constants
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "docs")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
EMBEDDING_CACHE_SIZE = int(os.getenv("EMBED_CACHE_SIZE", "256"))


# Clientes y modelos globales
qdrant = QdrantClient(url=QDRANT_HOST)
embed_model = SentenceTransformer("BAAI/bge-m3")
app = FastAPI(title="Multi-LLM RAG API")
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

# --- Abstracción de Proveedores ---

class LLMProvider(Protocol):
    async def generate(self, prompt: str, temperature: float, max_length: int) -> str:
        ...

class OllamaProvider:
    async def generate(self, prompt: str, temperature: float, max_length: int) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature,
            "max_length": max_length
        }
        async with semaphore:
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                r = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload)
                if r.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Ollama error: {r.text}")
                return r.json().get("response", "")

class OpenAIProvider:
    async def generate(self, prompt: str, temperature: float, max_length: int) -> str:
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API Key not configured")
        
        payload = {
            "model": "gpt-4o-mini", # O el configurado
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_length
        }
        async with semaphore:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
                )
                if r.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"OpenAI error: {r.text}")
                return r.json()["choices"][0]["message"]["content"]

class GeminiProvider:
    async def generate(self, prompt: str, temperature: float, max_length: int) -> str:
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API Key not configured")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_length
            }
        }
        async with semaphore:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(url, json=payload)
                if r.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Gemini error: {r.text}")
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]

# Selección de proveedor
def get_llm_provider() -> LLMProvider:
    if LLM_PROVIDER == "openai":
        return OpenAIProvider()
    elif LLM_PROVIDER == "gemini":
        return GeminiProvider()
    return OllamaProvider()

llm = get_llm_provider()

# Debug: Inspect Qdrant Client
import sys
print(f"DEBUG: Qdrant client attributes: {dir(qdrant)}", file=sys.stderr)
try:
    import qdrant_client
    print(f"DEBUG: Qdrant client version: {qdrant_client.__version__}", file=sys.stderr)
except:
    pass

# --- Helpers ---

@lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
def _cached_encode(query: str) -> tuple:
    vec = embed_model.encode(query)
    return tuple(float(x) for x in vec)

def _extract_text_from_hit(hit) -> Optional[str]:
    payload = getattr(hit, "payload", {}) if hasattr(hit, "payload") else hit.get("payload", {})
    for key in ("text", "content", "body", "document"):
        v = payload.get(key)
        if v: return v
    return next((v for v in payload.values() if isinstance(v, str) and v), None)

def _truncate(s: str, max_chars: int) -> str:
    if not s: return ""
    return s if len(s) <= max_chars else s[:max_chars].rsplit(" ", 1)[0] + "..."

# --- Endpoints ---

@app.get("/ask")
async def ask(
    query: str = Query(...),
    k: int = DEFAULT_K,
    max_context_chars: int = DEFAULT_MAX_CONTEXT,
    temperature: float = DEFAULT_TEMPERATURE,
    max_length: int = DEFAULT_MAX_LENGTH,
    include_sources: bool = False
):
    print(f"INFO: Querying: {query} (k={k}, sources={include_sources})")
    # 1) Embedding
    try:
        vec = list(_cached_encode(query))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {e}")

    # 2) Buscar en Qdrant
    try:
        hits = await asyncio.to_thread(lambda: qdrant.search(
            collection_name="docs",
            query_vector=vec,
            limit=k,
            with_payload=True
        ))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DEBUG: Error in qdrant.search: {e}", file=sys.stderr)
        raise HTTPException(status_code=400, detail=f"Qdrant: {e}")

    # 3) Construir Contexto
    docs = []
    for hit in hits:
        text = _extract_text_from_hit(hit)
        if text: docs.append(_truncate(text, 1500))

    if docs:
        combined = "\n\n---\n\n".join(docs)
        if len(combined) > max_context_chars:
            combined = _truncate(combined, max_context_chars)
        prompt = (
            "Eres un asistente de voz. Usa el contexto para responder de forma breve y clara.\n\n"
            f"Contexto:\n{combined}\n\nPregunta: {query}\nRespuesta:"
        )
    else:
        prompt = f"Responde de forma breve y clara: {query}"

    # 4) Generar Respuesta con el proveedor seleccionado
    answer = await llm.generate(prompt, temperature=temperature, max_length=max_length)

    # 5) Fuentes
    sources = []
    for hit in hits:
        payload = getattr(hit, "payload", {}) if hasattr(hit, "payload") else hit.get("payload", {})
        sources.append({"id": getattr(hit, "id", None), "source": payload.get("source")})

    response = {"answer": answer}
    if include_sources:
        response["sources"] = sources
    return response

@app.post("/ingest")
async def ingest(
    text: str = Query(..., description="Texto a ingerir"),
    source: str = Query("unknown", description="Nombre del archivo o fuente")
):
    """Ingiere texto en la base de datos vectorial."""
    try:
        # 1. Chunking simple
        chunk_size = 500
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        points = []
        import uuid
        
        # 2. Embeddings y Preparación
        for chunk in chunks:
            vec = list(_cached_encode(chunk))
            points.append({
                "id": str(uuid.uuid4()),
                "vector": vec,
                "payload": {"text": chunk, "source": source}
            })
            
        # 3. Upsert a Qdrant
        # Asegurar que colección existe (idempotente)
        if not qdrant.collection_exists("docs"):
            qdrant.create_collection(
                collection_name="docs",
                vectors_config={"size": len(points[0]["vector"]), "distance": "Cosine"}
            )
            
        qdrant.upsert(collection_name="docs", points=points)
        
        return {"status": "success", "chunks_processed": len(chunks)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/purge")
async def purge_db():
    try:
        from qdrant_client.http import models
        qdrant.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=1024,  # BAAI/bge-m3 dim
                distance=models.Distance.COSINE
            )
        )
        return {"status": "success", "message": "Knowledge Base purged."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"provider": LLM_PROVIDER, "status": "ok"}
