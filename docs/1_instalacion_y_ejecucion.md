[← Volver al Índice Principal](../README.md)

# 🛠️ Requisitos de Instalación (Ubuntu 24.04)

*Nota: KodaVox V2 está diseñado y ha sido probado exhaustivamente sobre **Ubuntu 24.04 LTS**. Debería ser compatible con otras distribuciones basadas en Debian (como Ubuntu 22.04), pero los comandos de instalación listados asumen este entorno.*

Para que el motor pueda compilar las librerías de audio nativas en Linux, debes instalar las dependencias de desarrollo de PortAudio:

```bash
# 1. Instalar dependencias del sistema (CRUCIAL)
sudo apt-get update && sudo apt-get install -y portaudio19-dev python3-dev build-essential

# 2. Asegúrate de tener Docker y NVIDIA Container Toolkit instalados para el TTS
```

---

## ✅ Validaciones Previas (Checklist)

Antes de ejecutar el sistema, asegúrate de validar los siguientes puntos:

1. **Configuración del Entorno (.env):**
   - Copia el archivo `.env.example` a `.env`: `cp .env.example .env`
   - Configura los proveedores que vayas a usar. Si usas modelos de pago (OpenAI, Gemini, ElevenLabs), asegúrate de colocar tus **API Keys**.
2. **Requisitos de Software:**
   - **Python 3.10+**: Necesario para el motor backend (y el paquete `venv` para entornos virtuales).
   - **Node.js y npm**: Necesarios para poder instalar y ejecutar el Dashboard V2.
3. **Modelos Locales (Ollama):** *(Solo requerido si se usa un modelo LLM local)*
   - Si en tu `.env` tienes configurado `LLM_PROVIDER=ollama`, verifica que el servicio de Ollama esté ejecutándose (`http://127.0.0.1:11434`).
   - Asegúrate de haber descargado el modelo definido en `OLLAMA_MODEL` ejecutando: `ollama pull qwen2.5:1.5b` (o el modelo que hayas elegido).
4. **Dependencias de TTS (Docker):**
   - Si vas a utilizar `TTS_PROVIDER=xtts`, el sistema requiere **Docker** y el plugin **Docker Compose**. *(El script `start_v2.sh` validará su existencia y los instalará automáticamente si no se encuentran en sistemas compatibles con apt).*
   - *(Opcional)* Si usas Piper localmente (`TTS_PROVIDER=piper`), el script `start_v2.sh` descargará automáticamente los modelos requeridos la primera vez si no existen.

---

## ⚡ Ejecución del Sistema

Puedes iniciar KodaVox V2 de dos formas: en primer plano (ideal para pruebas y desarrollo) o en segundo plano usando PM2 (recomendado para producción).

### Opción A: Ejecución Manual (Primer Plano)

Levanta todo el entorno (Docker, Venv, Motor y Dashboard) con un solo comando. Verás los logs directamente en tu consola.

```bash
# Otorga permisos de ejecución si es la primera vez
chmod +x start_v2.sh

# Ejecuta el script
./start_v2.sh
```

### Opción B: Ejecución en Producción con PM2 (Segundo Plano)

Para mantener KodaVox corriendo de forma ininterrumpida, gestionar sus logs y reiniciarlo si hay fallos, usaremos **PM2**.

1. **Instalar PM2 globalmente** (si no lo tienes):
   ```bash
   sudo npm install -g pm2
   ```
2. **Iniciar el sistema** utilizando el archivo `ecosystem.json` incluido:
   ```bash
   pm2 start ecosystem.json
   ```
3. **Comandos útiles de PM2**:
   - Ver el estado del sistema: `pm2 status`
   - Ver los logs en tiempo real: `pm2 logs kodavox-v2`
   - Detener el sistema: `pm2 stop kodavox-v2`
   - Hacer que el sistema inicie automáticamente al reiniciar el servidor:
     ```bash
     pm2 startup
     pm2 save
     ```

### ¿Qué hace `start_v2.sh` por debajo?
1. Valida e instala Docker si es necesario, y levanta el contenedor de **XTTS** (si aplica).
2. Crea y configura un entorno virtual de Python (`venv`) en la carpeta `orchestrator/`.
3. Instala los requerimientos de Python.
4. Inicia el **Motor Monolítico** (`core_engine.py`) en el puerto 5000.
5. Inicia el **Dashboard V2** en el puerto 5173.
