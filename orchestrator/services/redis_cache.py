import os
import json
import base64
import re
import unicodedata
from typing import Optional, Tuple, Dict, Any

class RedisCacheService:
    def __init__(self, host: str = None, port: int = None, db: int = 0):
        self.host = host or os.getenv("REDIS_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.db = db
        self.redis_client = None
        self._available = False
        self.connect()

    def connect(self):
        """Intenta conectar a Redis; si falla, desactiva el servicio sin interrumpir la app."""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                decode_responses=False
            )
            # Test ping
            self.redis_client.ping()
            self._available = True
            print(f"[Redis Cache] Conectado exitosamente a {self.host}:{self.port}")
        except Exception as e:
            self._available = False
            self.redis_client = None
            print(f"[Redis Cache Warning] No se pudo conectar a Redis ({e}). Modo Caché desactivado (Fallback directo a APIs).")

    def is_available(self) -> bool:
        return self._available

    def _normalize_key(self, text: str) -> str:
        """Limpia el texto eliminando acentos, puntuación y espacios extras para maximizar Hits de Caché."""
        text = text.lower().strip()
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return f"kodavox:qa:{text}"

    def get(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Recupera el objeto guardado en caché si existe.
        Retorna un dict con:
        {
            "text": str,          # Respuesta de texto
            "audio": bytes        # Audio PCM binario sintetizado (opcional)
        }
        """
        if not self._available or not self.redis_client:
            return None

        try:
            key = self._normalize_key(prompt)
            data_bytes = self.redis_client.get(key)
            if data_bytes:
                payload = json.loads(data_bytes.decode('utf-8'))
                audio_bytes = base64.b64decode(payload["audio_b64"]) if payload.get("audio_b64") else None
                print(f"[Redis Cache HIT] Pregunta encontrada en memoria: '{prompt[:30]}...'")
                return {
                    "text": payload.get("text", ""),
                    "audio": audio_bytes
                }
        except Exception as e:
            print(f"[Redis Cache Error] Error al leer caché: {e}")
        return None

    def set(self, prompt: str, response_text: str, audio_bytes: Optional[bytes] = None, ttl_seconds: int = 604800):
        """
        Guarda la pregunta, respuesta y audio binario PCM en Redis.
        TTL por defecto: 7 días (604,800 segundos).
        """
        if not self._available or not self.redis_client:
            return

        try:
            key = self._normalize_key(prompt)
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8') if audio_bytes else ""
            
            payload = {
                "prompt": prompt,
                "text": response_text,
                "audio_b64": audio_b64
            }
            
            self.redis_client.setex(key, ttl_seconds, json.dumps(payload))
            print(f"[Redis Cache STORE] Guardado en caché (TTL: {ttl_seconds}s): '{prompt[:30]}...'")
        except Exception as e:
            print(f"[Redis Cache Error] Error al escribir en caché: {e}")

redis_cache = RedisCacheService()
