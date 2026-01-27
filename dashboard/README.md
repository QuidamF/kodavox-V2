# 🎛️ Dashboard de Gestión - Voice Orchestrator

Este módulo proporciona una interfaz gráfica moderna para configurar y monitorear todo el ecosistema del orquestador de voz.

## Características

- **Monitor de Estado**: Visualización en tiempo real del flujo de voz (Escuchando, Procesando, Hablando).
- **Gestor RAG**: Subida y eliminación de documentos para el cerebro del asistente.
- **Configuración de IA**: Switch dinámico entre Ollama, OpenAI y Gemini.
- **Clonación de Voz**: Panel para subir muestras `.wav` y seleccionar la voz activa para el TTS.
- **Pruebas Unitarias**: Sistema de diagnóstico para validar la salud de STT, TTS y RAG de forma independiente.
- **Control de Sistema**: Botón de reinicio global para refrescar los servicios.

## Estructura Técnica

- **Frontend**: React + Vite + Tailwind CSS 4.
- **Estilo**: Estética *Glassmorphism* con animaciones de Framer Motion.
- **Backend**: FastAPI (Python) que actúa como puente entre la interfaz y el sistema de archivos / .env.
- **Comunicación**: WebSockets (Socket.IO) para el estado en tiempo real y REST para configuraciones.

## Configuración de Desarrollo

Si deseas ejecutar el frontend fuera de Docker para desarrollo:

1.  Instala dependencias:
    ```bash
    cd dashboard/frontend
    npm install
    ```
2.  Inicia el servidor de desarrollo:
    ```bash
    npm run dev
    ```

El backend de gestión debe estar corriendo para que el frontend funcione (normalmente vía Docker en el puerto 8080).

---
*Este módulo es parte del [Ecosistema Voice Orchestrator](../README.md).*
