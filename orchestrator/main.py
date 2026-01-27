import asyncio
import signal
import sys
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

    signal.signal(signal_handler, signal.getsignal(signal.SIGINT))

    # Iniciar orquestador
    orchestrator.start()

    # Mantener el loop de eventos corriendo (y servir Socket.IO si se desea)
    # Por ahora solo mantenemos el proceso vivo
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
