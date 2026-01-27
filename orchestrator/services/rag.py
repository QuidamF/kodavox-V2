import requests
from ..config import Config

class RAGServiceAdapter:
    def __init__(self):
        self.uri = Config.RAG_URI

    def query(self, text: str) -> str:
        """Envía una pregunta al servicio RAG y retorna la respuesta."""
        if not text:
            return ""
            
        print(f"[RAGService] Querying: {text}...")
        try:
            params = {"query": text} 
            
            response = requests.get(self.uri, params=params)
            response.raise_for_status()
            
            data = response.json()
            answer = data.get("answer", data.get("response", ""))
            
            print(f"[RAGService] Answer: {answer[:50]}...")
            return answer
        except Exception as e:
            print(f"[RAGService] Error: {e}")
            return "Lo siento, tuve un problema al consultar mi base de conocimientos."
