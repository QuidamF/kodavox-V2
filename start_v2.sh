#!/bin/bash

echo "=================================================="
echo "   Iniciando KodaVox V2 (Active Speech)           "
echo "=================================================="

# Helper function for progress spinner
show_spinner() {
    local pid=$1
    local delay=0.25
    local spinstr='|/-\'
    while kill -0 "$pid" 2>/dev/null; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

if [ ! -f ".env" ]; then
    echo "=================================================="
    echo " 🛠️ Asistente de Configuración Inicial KodaVox V2 "
    echo "=================================================="
    echo "No se encontró el archivo .env."
    echo -n "¿Deseas ejecutar el asistente para crearlo automáticamente? (s/N): "
    read -r resp
    if [[ "$resp" =~ ^[Ss] ]]; then
        cp .env.example .env
        echo ""
        echo "¿Qué tipo de instalación deseas?"
        echo "1) Full (Local): Requiere más RAM/GPU. Todo corre en tu máquina (Ollama, Whisper, Piper)."
        echo "2) Minimal (Nube): Muy rápido, requiere bajo hardware. Usa APIs externas (OpenAI, ElevenLabs)."
        echo "3) Personalizado: Preguntar módulo por módulo."
        echo -n "Selecciona una opción (1/2/3) [3]: "
        read -r install_type
        
        if [ "$install_type" = "1" ]; then
            sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=ollama/' .env
            sed -i 's/^STT_PROVIDER=.*/STT_PROVIDER=whisper/' .env
            sed -i 's/^TTS_PROVIDER=.*/TTS_PROVIDER=piper/' .env
            echo "   -> Perfil Full (Local) aplicado."
        elif [ "$install_type" = "2" ]; then
            sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=openai/' .env
            sed -i 's/^STT_PROVIDER=.*/STT_PROVIDER=elevenlabs/' .env
            sed -i 's/^TTS_PROVIDER=.*/TTS_PROVIDER=elevenlabs/' .env
            echo "   -> Perfil Minimal (Nube) aplicado."
        else
            echo ""
            echo "--- LLM (Cerebro) ---"
            echo "1) Local (Ollama)  2) Cloud (OpenAI)  3) Cloud (Gemini)"
            echo -n "Selección [1]: "
            read -r llm_choice
            case $llm_choice in
                2) sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=openai/' .env ;;
                3) sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=gemini/' .env ;;
                *) sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=ollama/' .env ;;
            esac
            
            echo ""
            echo "--- STT (Oído) ---"
            echo "1) Local (Whisper)  2) Cloud (ElevenLabs Scribe)"
            echo -n "Selección [1]: "
            read -r stt_choice
            case $stt_choice in
                2) sed -i 's/^STT_PROVIDER=.*/STT_PROVIDER=elevenlabs/' .env ;;
                *) sed -i 's/^STT_PROVIDER=.*/STT_PROVIDER=whisper/' .env ;;
            esac
            
            echo ""
            echo "--- TTS (Voz) ---"
            echo "1) Local (Piper - Muy Rápido)  2) Docker (XTTS - Clonación Avanzada)  3) Cloud (ElevenLabs)  4) Apagado"
            echo -n "Selección [1]: "
            read -r tts_choice
            case $tts_choice in
                2) sed -i 's/^TTS_PROVIDER=.*/TTS_PROVIDER=xtts/' .env ;;
                3) sed -i 's/^TTS_PROVIDER=.*/TTS_PROVIDER=elevenlabs/' .env ;;
                4) sed -i 's/^TTS_PROVIDER=.*/TTS_PROVIDER=off/' .env ;;
                *) sed -i 's/^TTS_PROVIDER=.*/TTS_PROVIDER=piper/' .env ;;
            esac
            echo "   -> Perfil Personalizado aplicado."
        fi
        echo "=================================================="
        echo "¡Archivo .env generado con éxito!"
        echo "Por favor, recuerda agregar tus API Keys en el archivo .env si elegiste proveedores en la Nube."
        echo "Iniciando sistema con la configuración elegida..."
        echo "=================================================="
    else
        echo "Por favor, crea tu archivo .env manualmente a partir de .env.example."
        exit 1
    fi
fi

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
ORIGINAL_PORT=$ENGINE_PORT

echo "[2/4] Verificando disponibilidad del puerto..."
while (echo > /dev/tcp/127.0.0.1/$ENGINE_PORT) >/dev/null 2>&1; do
    echo "   -> Puerto $ENGINE_PORT ocupado, intentando con $((ENGINE_PORT+1))..."
    ENGINE_PORT=$((ENGINE_PORT+1))
done

if [ "$ENGINE_PORT" -ne "$ORIGINAL_PORT" ]; then
    echo "   -> Puerto libre encontrado: $ENGINE_PORT. Guardando en .env..."
    if [ -f ".env" ]; then
        if grep -q "^ENGINE_PORT=" .env; then
            sed -i "s/^ENGINE_PORT=.*/ENGINE_PORT=$ENGINE_PORT/" .env
        else
            echo "ENGINE_PORT=$ENGINE_PORT" >> .env
        fi
    fi
fi

export VITE_ENGINE_PORT="$ENGINE_PORT"
echo "[2/4] Configurando Motor Monolítico..."

# Instalar dependencias del sistema (PortAudio y FFmpeg) si es necesario para PyAudio
if command -v apt-get &> /dev/null; then
    if ! dpkg -s portaudio19-dev &> /dev/null || ! dpkg -s ffmpeg &> /dev/null; then
        echo "   -> Instalando dependencias del sistema (PortAudio y FFmpeg)..."
        sudo apt-get update && sudo apt-get install -y portaudio19-dev ffmpeg
    fi
elif command -v brew &> /dev/null; then
    if ! brew ls --versions portaudio &> /dev/null || ! brew ls --versions ffmpeg &> /dev/null; then
        echo "   -> Instalando dependencias del sistema (PortAudio y FFmpeg) vía Homebrew..."
        brew install portaudio ffmpeg
    fi
fi

cd orchestrator
if [ ! -d "venv" ]; then
    echo "   -> Creando entorno virtual Python (venv)..."
    python3 -m venv venv
fi
source venv/bin/activate

# Determinar archivos de requerimientos a instalar
REQ_FILES="requirements.txt"
if [ "$STT_PROVIDER" = "whisper" ] || [ "$TTS_PROVIDER" = "piper" ]; then
    REQ_FILES="requirements.txt requirements-ml.txt"
fi

if [ ! -f ".requirements.md5" ] || ! md5sum -c .requirements.md5 &>/dev/null; then
    echo -n "   -> Instalando/Verificando dependencias de Python Base..."
    pip install --default-timeout=1000 -q -r requirements.txt &
    show_spinner $!
    
    if [[ "$REQ_FILES" == *"requirements-ml.txt"* ]]; then
        echo ""
        echo -n "   -> Instalando dependencias pesadas de IA Local (Torch, Whisper, etc.)..."
        pip install --default-timeout=1000 -q -r requirements-ml.txt &
        show_spinner $!
    fi
    
    md5sum $REQ_FILES > .requirements.md5
    echo " ¡Listo!"
fi

echo "[3/4] Iniciando main.py (Modular Core) en el puerto $ENGINE_PORT..."
# Corremos el motor mostrando salida en tiempo real
python main.py > >(tee engine.log) 2>&1 &
ENGINE_PID=$!
cd ..

# 3. Configurar e Iniciar Dashboard Vite
echo "[4/4] Configurando Dashboard..."
cd dashboard-v2
    install_node() {
        echo -n "   -> ¿Deseas instalar/actualizar Node.js (v20) automáticamente ahora? (s/N): "
        read -r resp
        if [[ "$resp" =~ ^[Ss] ]]; then
            if command -v apt-get &> /dev/null && command -v curl &> /dev/null; then
                echo "   -> Descargando script de NodeSource (Node 20)..."
                curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
                sudo apt-get install -y nodejs
                echo "   -> Instalación completada: $(node -v)"
            else
                echo "   -> ❌ ERROR: No se puede instalar automáticamente en este sistema (se requiere apt y curl)."
                echo "   -> Por favor, instala Node.js >= 18 manualmente."
                kill $ENGINE_PID 2>/dev/null
                exit 1
            fi
        else
            echo "   -> Operación cancelada. Por favor instala Node.js >= 18 manualmente."
            kill $ENGINE_PID 2>/dev/null
            exit 1
        fi
    }

    if ! command -v npm &> /dev/null || ! command -v node &> /dev/null; then
        echo "   -> ❌ ERROR: No se encontró 'npm' o Node.js en tu sistema."
        install_node
    else
        NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
        if [ "$NODE_VERSION" -lt 18 ]; then
            echo "   -> ❌ ERROR: La versión de Node.js instalada ($(node -v)) es muy antigua (se requiere >= 18)."
            install_node
        fi
    fi
    if [ ! -d "node_modules" ]; then
        echo -n "   -> Instalando dependencias de Node.js (esto puede tomar un momento)"
        npm install --silent &
        show_spinner $!
        echo " ¡Listo!"
    fi
    echo "   -> Iniciando Vite Server..."
    npm run dev &
    VITE_PID=$!
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
