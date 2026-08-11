import os
import json
import httpx
from abc import ABC, abstractmethod
from typing import AsyncGenerator

DEFAULT_SYSTEM_PROMPT = "Eres un asistente de voz llamado KodaVox. Responde en español latino de forma breve y natural."


class BaseLLMProvider(ABC):
    """Interfaz base para proveedores de LLM con streaming."""

    def __init__(self, provider_name: str, model_name: str):
        self.provider_name = provider_name
        self.model_name = model_name

    @abstractmethod
    async def generate_stream(
        self, prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT, history: list = None
    ) -> AsyncGenerator[str, None]:
        """Genera una respuesta en streaming token a token."""
        yield ""


class OllamaProvider(BaseLLMProvider):
    """Adaptador para Ollama en local."""

    def __init__(self):
        host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        super().__init__("ollama", model)
        self.url = f"{host}/api/generate"

    async def generate_stream(
        self, prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT, history: list = None
    ) -> AsyncGenerator[str, None]:
        history = history or []
        history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])
        if history_text:
            full_prompt = f"{system_prompt}\n\nHistorial:\n{history_text}\n\nUsuario: {prompt}"
        else:
            full_prompt = f"{system_prompt}\n\nUsuario: {prompt}"
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", self.url, json=payload, timeout=60.0) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                continue
        except Exception as error:
            print(f"[LLM Error - Ollama] {error}")
            yield f"Error al comunicarse con Ollama: {error}"


class OpenAIProvider(BaseLLMProvider):
    """Adaptador para OpenAI Chat Completions API."""

    def __init__(self):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        super().__init__("openai", model)
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.url = "https://api.openai.com/v1/chat/completions"

    async def generate_stream(
        self, prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT, history: list = None
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            print("[LLM Error - OpenAI] OPENAI_API_KEY no configurada.")
            yield "Error: OPENAI_API_KEY no está configurada en las variables de entorno."
            return

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        history = history or []
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", self.url, headers=headers, json=payload, timeout=60.0) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        print(f"[LLM Error - OpenAI] HTTP {response.status_code}: {error_body.decode('utf-8')}")
                        yield f"Error OpenAI ({response.status_code}). Verifica tu API key o cuota."
                        return

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue

                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    yield token
                        except json.JSONDecodeError:
                            continue
        except Exception as error:
            print(f"[LLM Error - OpenAI] {error}")
            yield f"Error al comunicarse con OpenAI: {error}"


class GeminiProvider(BaseLLMProvider):
    """Adaptador para Google Gemini API usando google-genai."""

    def __init__(self):
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        super().__init__("gemini", model)
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    async def generate_stream(
        self, prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT, history: list = None
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            print("[LLM Error - Gemini] GEMINI_API_KEY no configurada.")
            yield "Error: GEMINI_API_KEY no está configurada en las variables de entorno."
            return

        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.api_key)
            
            history = history or []
            contents = []
            for msg in history:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
            
            response_stream = await client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                )
            )
            
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text

        except ImportError:
            print("[LLM Error - Gemini] Falta la librería 'google-genai'.")
            yield "Error: Instala google-genai ('pip install google-genai')."
        except Exception as error:
            print(f"[LLM Error - Gemini] {error}")
            yield f"Error al comunicarse con Gemini: {error}"


class LLMFactory:
    """Fábrica para obtener el proveedor de LLM activo."""

    @staticmethod
    def get_provider(provider_name: str = None) -> BaseLLMProvider:
        name = (provider_name or os.getenv("LLM_PROVIDER", "ollama")).lower()
        if name == "ollama":
            return OllamaProvider()
        elif name == "openai":
            return OpenAIProvider()
        elif name == "gemini":
            return GeminiProvider()
        else:
            print(f"[LLMFactory] Proveedor '{name}' desconocido. Usando Ollama por defecto.")
            return OllamaProvider()
