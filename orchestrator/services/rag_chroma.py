import os
import uuid
import chromadb
from pypdf import PdfReader
from typing import List, Dict, Any, Optional

CHROMA_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")

class ChromaRAGService:
    def __init__(self):
        # Asegurar que el directorio de almacenamiento exista
        os.makedirs(CHROMA_DATA_DIR, exist_ok=True)
        # Inicializar el cliente persistente de ChromaDB
        self.client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
        print(f"[RAG Chroma] Cliente inicializado en {CHROMA_DATA_DIR}")

    def list_collections(self) -> List[str]:
        """Lista los nombres de todas las colecciones existentes."""
        collections = self.client.list_collections()
        return [col.name for col in collections]

    def create_collection(self, name: str):
        """Crea una nueva colección (Base de Conocimiento)."""
        # get_or_create_collection evita lanzar error si ya existe
        self.client.get_or_create_collection(name=name)
        print(f"[RAG Chroma] Colección '{name}' asegurada.")

    def delete_collection(self, name: str):
        """Elimina una colección existente."""
        try:
            self.client.delete_collection(name=name)
            print(f"[RAG Chroma] Colección '{name}' eliminada.")
        except Exception as e:
            print(f"[RAG Chroma] Error al eliminar colección '{name}': {e}")

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Divide un texto largo en fragmentos más pequeños (chunks)."""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
            
        return chunks

    def process_file_content(self, filename: str, content: bytes) -> str:
        """Extrae el texto del contenido binario de un archivo según su extensión."""
        ext = filename.split(".")[-1].lower()
        
        if ext == "pdf":
            import io
            reader = PdfReader(io.BytesIO(content))
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text
            
        elif ext in ["txt", "md", "json", "csv"]:
            return content.decode("utf-8", errors="ignore")
            
        else:
            raise ValueError(f"Formato no soportado: .{ext}")

    def add_document(self, collection_name: str, filename: str, content: bytes):
        """Procesa, fragmenta e indexa un documento en una colección."""
        collection = self.client.get_or_create_collection(name=collection_name)
        
        # 1. Extraer texto
        text = self.process_file_content(filename, content)
        if not text.strip():
            raise ValueError("El documento no contiene texto extraíble.")
            
        # 2. Fragmentar texto (Chunking)
        chunks = self._chunk_text(text)
        
        # 3. Preparar datos para ChromaDB
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]
        
        # 4. Insertar en ChromaDB (calcula embeddings por defecto automáticamente)
        collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[RAG Chroma] Añadidos {len(chunks)} fragmentos de '{filename}' a '{collection_name}'.")

    def get_relevant_context(self, collection_name: str, query: str, top_k: int = 3) -> str:
        """Busca fragmentos relevantes en la colección y los devuelve formateados como contexto."""
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception as e:
            print(f"[RAG Chroma] No se pudo obtener la colección '{collection_name}': {e}")
            return ""
            
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        if not results["documents"] or not results["documents"][0]:
            return ""
            
        # results["documents"] is a list of lists of strings
        docs = results["documents"][0]
        metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
        
        context_parts = []
        for i, doc in enumerate(docs):
            source = metas[i].get("source", "Desconocido")
            context_parts.append(f"--- Documento: {source} ---\n{doc}")
            
        return "\n\n".join(context_parts)
