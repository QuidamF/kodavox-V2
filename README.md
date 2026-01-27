# 🎙️ KodaVox Ecosystem

Bienvenido al ecosistema **KodaVox**. Este proyecto es una solución integral para crear asistentes de voz inteligentes, modulares y 100% locales (con opción a nube).

## ⚡ Inicio Automático (Windows)

He creado un script para que no tengas que levantar cada parte por separado:
1. Haz clic derecho sobre **`Start-System.ps1`** en la raíz.
2. Selecciona **"Ejecutar con PowerShell"**.

Este script levantará automáticamente Docker, verificará tus dependencias de Python e iniciará el orquestador en una nueva ventana.

---

## 🚀 Inicio Manual (Paso a Paso)

---

## 🏗️ Documentación Técnica

Para una comprensión profunda del sistema, revisa los siguientes documentos:

- **[🗺️ Arquitectura del Sistema](file:///c:/Users/JPM-PROGRAMACION/Documents/Proyectos/orquestador de voz/ARCHITECTURE.md)**: Diagramas Mermaid, patrones de diseño y especificaciones de hardware.
- **[🛠️ Guía de Instalación Detallada](file:///c:/Users/JPM-PROGRAMACION/Documents/Proyectos/orquestador de voz/README.md)**: Pasos detallados para configurar el entorno desde cero.

### 📦 Módulos Individuales
Cada componente tiene su propia documentación técnica:
- [🔹 Speech-to-Text (Whisper)](file:///c:/Users/JPM-PROGRAMACION/Documents/Proyectos/orquestador de voz/services/stt/README.md)
- [🔹 Text-to-Speech (XTTS)](file:///c:/Users/JPM-PROGRAMACION/Documents/Proyectos/orquestador de voz/services/tts/README.md)
- [🔹 RAG Engine (Conocimiento)](file:///c:/Users/JPM-PROGRAMACION/Documents/Proyectos/orquestador de voz/services/rag/README.md)
- [🔹 Dashboard de Gestión](file:///c:/Users/JPM-PROGRAMACION/Documents/Proyectos/orquestador de voz/dashboard/README.md)

---

## 💻 Requisitos de Sistema

- **Mínimo**: 16GB RAM | CPU 4 Cores.
- **Recomendado**: 32GB RAM | NVIDIA GPU con 8GB+ VRAM (RTX 3060+).
- **S.O.**: Windows 10/11 con Docker Desktop.

---

## 👥 Perfil Sugerido
Ideal para desarrolladores con experiencia en **Python (FastAPI)**, **Docker**, **IA (RAG/NLP)** y **React**.
