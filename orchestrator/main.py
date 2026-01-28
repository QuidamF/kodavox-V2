import asyncio
import signal
import sys
import uvicorn
from core.event_bus import EventBus
from core.state_manager import StateManager
from core.orchestrator import VoiceOrchestrator

async def main():
    # Inicializar componentes core
    bus = EventBus()
    state = StateManager(bus)
    
    # Inicializar Orquestador
    orchestrator = VoiceOrchestrator(bus, state)
    
    print("==========================================")
    print("   Iniciando Orquestador de Voz Modular   ")
    print("==========================================")

    # Manejar señales de interrupción (Ctrl+C)
    def signal_handler(sig, frame):
        print("\n[Main] Deteniendo sistema...")
        # Limpieza básica
        orchestrator.capturer.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Iniciar orquestador
    orchestrator.start()

    # Iniciar servidor Uvicorn para Socket.IO
    # Configurar uvicorn config
    config = uvicorn.Config(app=bus.app, host="0.0.0.0", port=5000, log_level="info")
    server = uvicorn.Server(config)

    print("[Main] Starting Uvicorn server for Socket.IO on port 5000...")
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
