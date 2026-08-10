import asyncio
import argparse
import sys
import os

# Permitir la importación del paquete orchestrator desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from orchestrator.services.llm_provider import LLMFactory


async def test_provider(provider_name: str, prompt: str):
    print(f"\n--- Probando Proveedor LLM: {provider_name.upper()} ---")
    provider = LLMFactory.get_provider(provider_name)
    print(f"Modelo configurado: {provider.model_name}")
    print(f"Prompt de prueba: \"{prompt}\"")
    print("Respuesta: ", end="", flush=True)

    token_count = 0
    async for token in provider.generate_stream(prompt):
        print(token, end="", flush=True)
        token_count += 1

    print(f"\n[Transmisión completada - {token_count} chunks/tokens recibidos]\n")


async def main():
    parser = argparse.ArgumentParser(description="Prueba los adaptadores de LLM en streaming (Ollama, OpenAI, Gemini)")
    parser.add_argument(
        "--provider",
        choices=["ollama", "openai", "gemini", "all"],
        default=os.getenv("LLM_PROVIDER", "ollama"),
        help="Proveedor a probar (por defecto usa LLM_PROVIDER de .env)",
    )
    parser.add_argument(
        "--prompt",
        default="Hola KodaVox, preséntate brevemente en una frase.",
        help="Prompt de prueba para enviar al LLM",
    )
    args = parser.parse_args()

    if args.provider == "all":
        for p in ["ollama", "openai", "gemini"]:
            await test_provider(p, args.prompt)
    else:
        await test_provider(args.provider, args.prompt)


if __name__ == "__main__":
    asyncio.run(main())
