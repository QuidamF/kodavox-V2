# 🎙️ KodaVox V2: Active Speech Engine

Bienvenido a **KodaVox V2**. Esta versión ha sido rediseñada desde cero para priorizar la **latencia mínima absoluta**, pasando de una arquitectura de microservicios distribuida a un **Motor Monolítico en Memoria** enfocado en una experiencia de "Habla Activa" (Active Speech) fluida.

Debido al crecimiento de las capacidades del sistema, la documentación ha sido dividida en módulos para facilitar su lectura y mantenimiento.

## 📚 Tabla de Contenidos

Por favor, consulta los siguientes documentos en la carpeta `docs/` para aprender a instalar, usar y personalizar tu agente:

1. **[Instalación y Ejecución](docs/1_instalacion_y_ejecucion.md)**
   - Requisitos del sistema (Probado en Linux/Ubuntu 24.04 LTS).
   - Validaciones de entorno (`.env` y dependencias).
   - Comandos para ejecutar en desarrollo o en producción (PM2).

2. **[Guía del Dashboard y Respaldo](docs/2_guia_dashboard.md)**
   - Interfaz web responsiva con autodescubrimiento de red (ideal para visualización móvil).
   - Explicación de los paneles de telemetría.
   - Configuración de personalidad y Wakeword.
   - Catálogo de Voces y Clonación ElevenLabs.
   - Base de Conocimientos (RAG).
   - **Exportación e Importación de Perfiles (ZIP) para migrar tu agente**.

3. **[Arquitectura y Desarrollo](docs/3_arquitectura_y_desarrollo.md)**
   - Diagrama de flujo completo (Mermaid).
   - Explicación del Motor Monolítico (Zero-Internal Latency).
   - Soporte Multi-STT (Faster-Whisper Local + ElevenLabs Scribe Cloud).
   - Notas clave para desarrolladores.

4. **[Integraciones y Hardware](docs/4_integraciones_y_hardware.md)**
   - Guía para vincular KodaVox con **Robot Face (Avatar)**.

5. **[Solución de Problemas (Troubleshooting)](docs/5_troubleshooting.md)**
   - Soluciones a problemas comunes de dependencias, Node, Docker y Memoria RAM.

---
*KodaVox V2 - Diseñado para ser rápido, local y extremadamente personalizable.*
