import requests
from config import Config

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
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print("[RAGService] Knowledge Base likely empty or missing collection.")
                return "No tengo información en mi cerebro aún. Por favor sube documentos en el Dashboard."
            print(f"[RAGService] HTTP Error: {e}")
            return "Tuve un error de conexión con mi cerebro."
        except Exception as e:
            print(f"[RAGService] Error: {e}")
            return "Lo siento, tuve un problema al consultar mi base de conocimientos."
