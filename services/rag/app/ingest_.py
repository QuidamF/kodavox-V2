from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
import os

QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost:6333")
qdrant = QdrantClient(url=QDRANT_HOST)
embed_model = SentenceTransformer("BAAI/bge-m3")

# Crear colección si no existe
if "docs" not in [c.name for c in qdrant.get_collections().collections]:
    qdrant.create_collection(
        collection_name="docs",
        vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE)
    )

# Ejemplo: documentos simples
docs = [
    {"id": 1, "text": "Qwen 2.5 es un modelo multilenguaje de alto rendimiento."},
    {"id": 2, "text": "FastAPI es un framework rápido para APIs en Python."}
]

# Ingestar documentos con embeddings
for doc in docs:
    emb = embed_model.encode(doc["text"]).tolist()
    qdrant.upsert(
        collection_name="docs",
        points=[models.PointStruct(id=doc["id"], vector=emb, payload=doc)]
    )

print("Documentos indexados en Qdrant.")
