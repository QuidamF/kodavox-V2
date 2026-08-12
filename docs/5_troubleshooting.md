[← Volver al Índice Principal](../README.md)

# ⚠️ Solución de Problemas (Troubleshooting)

Al desplegar el sistema en un entorno completamente nuevo, podrías encontrarte con los siguientes casos límite:

1. **Falla al instalar PyAudio (Librerías C ausentes)**
   - Si durante la instalación de dependencias ves un error rojo extenso relacionado con `portaudio.h`, significa que te saltaste la instalación de dependencias del sistema.
   - **Solución:** Ejecuta `sudo apt-get install portaudio19-dev python3-dev build-essential`.
2. **Paquete `venv` de Python no instalado**
   - En algunas distribuciones (como Ubuntu), Python 3 viene preinstalado, pero la librería para crear entornos aislados no. El script fallará al ejecutar `python3 -m venv venv`.
   - **Solución:** Ejecuta `sudo apt-get install python3-venv`.
3. **Falta de Node.js o npm**
   - El script `start_v2.sh` requiere estrictamente `npm` para levantar el Dashboard, ya que es a través de este que se configura el agente (RAG, cambio de voces, etc). Si no lo tienes, el script se abortará intencionalmente.
   - **Solución:** Instala Node.js y npm (`sudo apt-get install nodejs npm` o usa NVM).
4. **El Puerto del Backend está ocupado**
   - Si otro servicio está usando el puerto configurado (por defecto `5000`), el motor colapsará indicando `Address already in use`. A diferencia de Vite, el motor no cambia de puerto automáticamente.
   - **Solución:** Modifica la variable `ENGINE_PORT` en tu archivo `.env` por otro puerto libre (ej. `5001`).
5. **Instalación de Docker rechazada**
   - Si usas `TTS_PROVIDER=xtts` y no tienes Docker, el script intentará instalarlo vía `apt`. Si usas macOS, Fedora, o CentOS, la instalación fallará.
   - **Solución:** Instala Docker Desktop o Docker Engine manualmente para tu sistema operativo.
6. **Falta de Memoria RAM (Proceso "Killed")**
   - Si el sistema corre en un servidor con menos de 4GB de RAM y sin archivo Swap, el sistema operativo invocará al *OOM Killer* al cargar los modelos de lenguaje o STT en memoria, cerrando el proceso de Python repentinamente sin lanzar errores explícitos.
   - **Solución:** Añade un archivo de paginación (Swap) de 8GB o incrementa la RAM física del servidor.
