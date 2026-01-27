import socketio
import asyncio
from typing import Callable, Any

class EventBus:
    def __init__(self):
        self.sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
        self.app = socketio.ASGIApp(self.sio)
        self.listeners = {}

    async def emit(self, event: str, data: Any = None):
        """Emite un evento a todos los clientes conectados y listeners internos."""
        # Emitir a clientes socketio
        await self.sio.emit(event, data)
        
        # Emitir a listeners internos
        if event in self.listeners:
            for callback in self.listeners[event]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)

    def on(self, event: str, callback: Callable):
        """Registra un listener interno para un evento."""
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

    # Decorador para registrar eventos
    def event_handler(self, event: str):
        def decorator(func):
            self.on(event, func)
            return func
        return decorator
