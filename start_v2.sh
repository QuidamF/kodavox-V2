#!/bin/bash

echo "=================================================="
echo "   Iniciando KodaVox V2 (Active Speech)           "
echo "=================================================="

# El motor se ejecuta directamente desde este script, por lo que exportamos la
# configuración común que Docker Compose también lee desde .env.
if [ -f ".env" ]; then
    set -a
    . ./.env
    set +a
fi

# 1. Iniciar únicamente el proveedor de voz seleccionado.
TTS_PROVIDER="${TTS_PROVIDER:-xtts}"
TTS_SERVICE_STARTED=false
if [ "$TTS_PROVIDER" = "xtts" ]; then
    echo "[1/4] Iniciando servicio TTS (XTTS-v2) en Docker..."
    docker compose up -d tts-service
    TTS_SERVICE_STARTED=true

    # XTTS puede tardar varios minutos en descargar/cargar el modelo. No iniciamos
    # el motor hasta que su endpoint de salud pueda aceptar conexiones.
    TTS_HEALTH_URL="${TTS_HEALTH_URL:-http://127.0.0.1:8001/}"
    TTS_WAIT_SECONDS="${TTS_WAIT_SECONDS:-300}"
    echo "   -> Esperando a que TTS esté disponible (máximo ${TTS_WAIT_SECONDS}s)..."
    for ((elapsed = 0; elapsed < TTS_WAIT_SECONDS; elapsed += 2)); do
        if curl --fail --silent --output /dev/null --max-time 2 "$TTS_HEALTH_URL"; then
            echo "   -> TTS listo."
            break
        fi
        sleep 2
    done

    if ! curl --fail --silent --output /dev/null --max-time 2 "$TTS_HEALTH_URL"; then
        echo "ERROR: TTS no respondió en ${TTS_WAIT_SECONDS}s; el motor no se iniciará."
        echo "Últimos registros de tts-service:"
        docker compose logs --tail=50 tts-service
        exit 1
    fi
elif [ "$TTS_PROVIDER" = "piper" ]; then
    echo "[1/4] Usando Piper local; no se iniciará el contenedor XTTS."
elif [ "$TTS_PROVIDER" = "elevenlabs" ]; then
    echo "[1/4] Usando ElevenLabs (Nube); no se iniciará el contenedor XTTS."
elif [ "$TTS_PROVIDER" = "off" ]; then
    echo "[1/4] TTS desactivado; no se iniciará un proveedor de voz."
else
    echo "ERROR: TTS_PROVIDER inválido: $TTS_PROVIDER (usa xtts, piper, elevenlabs u off)."
    exit 1
fi

# 2. Configurar Entorno Python e Iniciar Motor Monolítico
echo "[2/4] Configurando Motor Monolítico..."
cd orchestrator
if [ ! -d "venv" ]; then
    echo "   -> Creando entorno virtual Python (venv)..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "[3/4] Iniciando core_engine.py en el puerto 5000..."
# Corremos el motor mostrando salida en tiempo real
python core_engine.py 2>&1 | tee engine.log &
ENGINE_PID=$!
cd ..

# 3. Configurar e Iniciar Dashboard Vite
echo "[4/4] Configurando Dashboard..."
cd dashboard-v2
if [ ! -d "node_modules" ]; then
    echo "   -> Instalando dependencias de Node.js..."
    npm install
fi
echo "   -> Iniciando Vite Server..."
npm run dev &
VITE_PID=$!
cd ..

echo ""
echo "=================================================="
echo " 🚀 Todo está corriendo exitosamente.             "
echo " 🌐 Abre el Dashboard: http://localhost:5173      "
echo " ⏹️  Presiona Ctrl+C en esta terminal para apagar todo."
echo "=================================================="

cleanup() {
    echo ""
    echo "Deteniendo procesos..."
    kill $ENGINE_PID 2>/dev/null
    kill $VITE_PID 2>/dev/null
    if [ "$TTS_SERVICE_STARTED" = true ]; then
        docker compose stop tts-service
    fi
    echo "KodaVox V2 apagado correctamente."
    exit 0
}

trap cleanup SIGINT SIGTERM
wait
