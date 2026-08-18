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

# 0. Iniciar Redis Cache (Servicio ligero en Docker)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "[0/4] Iniciando contenedor Redis Cache (memoria inteligente)..."
    docker compose up -d redis-cache
fi

# 1. Iniciar únicamente el proveedor de voz seleccionado.
TTS_PROVIDER="${TTS_PROVIDER:-xtts}"
TTS_SERVICE_STARTED=false
if [ "$TTS_PROVIDER" = "xtts" ]; then
    echo "[1/4] Iniciando servicio TTS (XTTS-v2) en Docker..."
    
    # Validar Docker y Docker Compose
    if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        echo "   -> Docker o el plugin Docker Compose no están instalados."
        echo "   -> Intentando instalar Docker automáticamente..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
            echo "   -> Instalación completada. (Es posible que debas cerrar sesión y volver a entrar para no requerir sudo)"
        else
            echo "   -> ERROR: No se puede instalar automáticamente en este sistema (requiere apt)."
            echo "      Por favor, instala Docker y Docker Compose manualmente."
            exit 1
        fi
    fi

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
    if [ -n "$PIPER_MODEL_PATH" ]; then
        MODEL_FULL_PATH="orchestrator/$PIPER_MODEL_PATH"
        if [ ! -f "$MODEL_FULL_PATH" ]; then
            echo "   -> Modelo Piper no encontrado en: $MODEL_FULL_PATH"
            echo "   -> Intentando descargar modelo de HuggingFace..."
            filename=$(basename "$PIPER_MODEL_PATH")
            # Parse filename to get language, region, voice and quality
            if [[ "$filename" =~ ^([a-z]{2})_([A-Z]{2})-([a-zA-Z0-9_]+)-([a-z_]+)\.onnx$ ]]; then
                lang="${BASH_REMATCH[1]}"
                region="${BASH_REMATCH[1]}_${BASH_REMATCH[2]}"
                voice="${BASH_REMATCH[3]}"
                quality="${BASH_REMATCH[4]}"
                
                mkdir -p "$(dirname "$MODEL_FULL_PATH")"
                
                base_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/${lang}/${region}/${voice}/${quality}"
                echo "      Descargando $filename..."
                curl -L -f -o "$MODEL_FULL_PATH" "${base_url}/${filename}"
                echo "      Descargando ${filename}.json..."
                curl -L -f -o "${MODEL_FULL_PATH}.json" "${base_url}/${filename}.json"
                echo "   -> Descarga de modelo completada."
            else
                echo "   -> ERROR: No se pudo inferir la URL de descarga para $filename."
                echo "      Por favor, descarga el modelo y su archivo .json manualmente."
            fi
        fi
    fi
elif [ "$TTS_PROVIDER" = "elevenlabs" ]; then
    echo "[1/4] Usando ElevenLabs (Nube); no se iniciará el contenedor XTTS."
elif [ "$TTS_PROVIDER" = "off" ]; then
    echo "[1/4] TTS desactivado; no se iniciará un proveedor de voz."
else
    echo "ERROR: TTS_PROVIDER inválido: $TTS_PROVIDER (usa xtts, piper, elevenlabs u off)."
    exit 1
fi

# 2. Configurar Entorno Python e Iniciar Motor Monolítico
ENGINE_PORT="${ENGINE_PORT:-5000}"
export VITE_ENGINE_PORT="$ENGINE_PORT"
echo "[2/4] Configurando Motor Monolítico..."
cd orchestrator
if [ ! -d "venv" ]; then
    echo "   -> Creando entorno virtual Python (venv)..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "[3/4] Iniciando core_engine.py en el puerto $ENGINE_PORT..."
# Corremos el motor mostrando salida en tiempo real
python core_engine.py 2>&1 | tee engine.log &
ENGINE_PID=$!
cd ..

# 3. Configurar e Iniciar Dashboard Vite
echo "[4/4] Configurando Dashboard..."
cd dashboard-v2
if ! command -v npm &> /dev/null; then
    echo "   -> ❌ ERROR: No se encontró 'npm' o Node.js en tu sistema."
    echo "   -> Aunque el motor puede correr de forma 'Headless', el Dashboard es estrictamente necesario para configurar al Agente KodaVox (RAG, Voces, etc)."
    echo "   -> Por favor, instala Node.js y npm, y vuelve a ejecutar este script."
    # Matar el motor que ya habíamos levantado en el paso anterior
    kill $ENGINE_PID 2>/dev/null
    exit 1
else
    if [ ! -d "node_modules" ]; then
        echo "   -> Instalando dependencias de Node.js..."
        npm install
    fi
    echo "   -> Iniciando Vite Server..."
    npm run dev &
    VITE_PID=$!
fi
cd ..

echo ""
echo "=================================================="
echo " 🚀 Sistema iniciado.                             "
echo " 🌐 Dashboard: http://localhost:5173 (o puerto consecutivo si está ocupado)"
echo " 🔌 Motor Core: http://localhost:$ENGINE_PORT"
echo " ⏹️  Presiona Ctrl+C en esta terminal para apagar."
echo "=================================================="

cleanup() {
    echo ""
    echo "Deteniendo procesos..."
    kill $ENGINE_PID 2>/dev/null
    if [ -n "$VITE_PID" ]; then
        kill $VITE_PID 2>/dev/null
    fi
    if [ "$TTS_SERVICE_STARTED" = true ]; then
        docker compose stop tts-service
    fi
    echo "KodaVox V2 apagado correctamente."
    exit 0
}

trap cleanup SIGINT SIGTERM
wait
