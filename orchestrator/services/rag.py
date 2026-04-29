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

    async def query_stream(self, text: str):
        """Envía una pregunta al servicio RAG y retorna un generador de tokens asincrono."""
        if not text:
            return
            
        print(f"[RAGService] Querying Stream: {text}...")
        import httpx
        import urllib.parse
        
        parsed_uri = urllib.parse.urlparse(self.uri)
        stream_uri = f"{parsed_uri.scheme}://{parsed_uri.netloc}/ask/stream"
        
        try:
            params = {"query": text} 
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", stream_uri, params=params, timeout=300.0) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk
        except Exception as e:
            print(f"[RAGService] Streaming Error: {e}")
            yield "Hubo un error al pensar la respuesta."
