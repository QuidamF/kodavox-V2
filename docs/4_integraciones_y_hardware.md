[← Volver al Índice Principal](../README.md)

# 🤖 Integraciones y Hardware

## Integración con Robot Face (Avatar)
KodaVox V2 incluye soporte nativo para el proyecto **Robot Face (OctopID)**. KodaVox actúa como el "cerebro" y controla directamente las expresiones y el lip-sync de la cara.

Para usarlo:
1. Inicia tu backend original de Robot Face (`audioServer.py` y `app_fastapi.py`).
2. Abre tu interfaz `face.html`.
3. En el Dashboard V2 de KodaVox, ve a la pestaña **Diagnósticos**.
4. Activa la opción **Sincronización de Estados (Robot Face)**.

*La sincronización labial (Lip-Sync) funcionará de forma automática ya que tu `audioServer.py` escucha la salida nativa de KodaVox mediante loopback de sistema.*
