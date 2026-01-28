import socketio
import asyncio
from typing import Callable, Any

class EventBus:
    def __init__(self):
        self.sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
        self.app = socketio.ASGIApp(self.sio)
        self.listeners = {}

        # Bridge socketio events to internal listeners
        @self.sio.on('*')
        async def catch_all(event, sid, data):
            # Ignorar eventos de conexión/desconexión en este catch-all si es necesario
            if event in self.listeners:
                print(f"[EventBus] Received socket event '{event}' from frontend")
                for callback in self.listeners[event]:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)

    async def emit(self, event: str, data: Any = None):
        """Emite un evento a todos los clientes conectados y listeners internos."""
        
        # 1. PRIORIDAD: Emitir a listeners internos PRIMERO
        # Esto asegura que el "cerebro" (Orquestador) reaccione aunque la UI (SocketIO) falle/bloquee
        if event in self.listeners:
            if event != "audio_chunk":
                 print(f"[EventBus] Dispatching '{event}' to {len(self.listeners[event])} listeners")
            for callback in self.listeners[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    print(f"[EventBus] Error in internal listener for {event}: {e}")
        else:
             if event != "audio_chunk":
                 print(f"[EventBus] No internal listeners for '{event}'")

        # 2. Emitir a clientes socketio (UI) de forma NO BLOQUEANTE (Fire-and-forget)
        # Usamos create_task para que si el socket cuelga, no detenga el sistema.
        try:
            await self.sio.emit(event, data)
        except Exception as e:
             print(f"[EventBus] SocketIO emit error: {e}")

    def on(self, event: str, callback: Callable):
        """Registra un listener interno para un evento."""
        print(f"[EventBus] Registering listener for '{event}'")
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

    # Decorador para registrar eventos
    def event_handler(self, event: str):
        def decorator(func):
            self.on(event, func)
            return func
        return decorator
