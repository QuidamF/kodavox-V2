"""
Shim de compatibilidad para evitar romper cualquier script antiguo que importe MonolithicEngine.
Re-exporta la nueva implementación modular desde core.pipeline y main.
"""
from core.pipeline import EnginePipeline as MonolithicEngine
from main import pipeline as engine, app, socket_app

__all__ = ["MonolithicEngine", "engine", "app", "socket_app"]
