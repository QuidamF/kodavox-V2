from fastapi import FastAPI, Query, HTTPException
import requests
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost:6333")

# Conectar con Qdrant y embeddings
qdrant = QdrantClient(url=QDRANT_HOST)
embed_model = SentenceTransformer("BAAI/bge-m3")

app = FastAPI()

@app.get("/ask")
def ask(query: str = Query(...), k: int = 3):
    try:
        vec = embed_model.encode(query).tolist()
        # No pedimos payload pesado
        hits = qdrant.search(
            collection_name="docs",
            query_vector=vec,
            limit=k,
            with_payload=True,       # <---- clave: no devuelve 'text'
            with_vectors=False
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Qdrant: {e}")

    # Construye un prompt breve (sin incluir el texto recuperado)
    # prompt = (
    #     "Responde de forma concisa. Si no sabes la respuesta por falta de información, "
    #     "di explícitamente: 'No lo sé con base en el material disponible.'\n\n"
    #     f"Pregunta: {query}\nRespuesta:"
    # )

    context = "\n".join([hit.payload["text"] for hit in hits])
    prompt = f"Usa el siguiente contexto para responder:\n{context}\n\nPregunta: {query}\nRespuesta:"


    r = requests.post(f"{OLLAMA_HOST}/api/generate", json={
        "model": "qwen2.5:7b",
        "prompt": prompt,
        "stream": False
    })
    data = r.json()
    return {"answer": data.get("response", "")}