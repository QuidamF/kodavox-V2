from enum import Enum, auto
from .event_bus import EventBus
import asyncio

class AppState(Enum):
    IDLE = auto()
    LISTENING_WAKEWORD = auto()
    LISTENING_USER = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()

class StateManager:
    def __init__(self, event_bus: EventBus):
        self.state = AppState.IDLE
        self.bus = event_bus
        self.context = {}

    async def set_state(self, new_state: AppState):
        """Cambia el estado y notifica mediante el EventBus."""
        old_state = self.state
        self.state = new_state
        print(f"[StateManager] State changed: {old_state.name} -> {self.state.name}")
        
        await self.bus.emit("state_changed", {
            "from": old_state.name,
            "to": self.state.name
        })

    def get_state(self) -> AppState:
        return self.state

    def update_context(self, key: str, value: any):
        """Actualiza el contexto global de la conversación."""
        self.context[key] = value
        
    def get_context(self, key: str):
        return self.context.get(key)
