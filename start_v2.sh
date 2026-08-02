#!/bin/bash

echo "=================================================="
echo "   Iniciando KodaVox V2 (Active Speech)           "
echo "=================================================="

# 1. Levantar microservicio TTS con Docker Compose
echo "[1/4] Iniciando servicio TTS (XTTS-v2) en Docker..."
docker compose up -d tts-service

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
    docker compose stop
    echo "KodaVox V2 apagado correctamente."
    exit 0
}

trap cleanup SIGINT SIGTERM
wait
