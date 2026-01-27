# Start-System.ps1
# Script para iniciar el ecosistema de KodaVox en un solo paso.

Write-Host "🚀 Iniciando KodaVox Ecosystem..." -ForegroundColor Cyan

# 1. Verificar .env
if (-not (Test-Path ".env")) {
    Write-Host "⚠️ Error: No se encontró el archivo .env en la raíz." -ForegroundColor Red
    Write-Host "Por favor, crea uno basado en .env.example antes de continuar."
    exit
}

# 2. Levantar Microservicios (Docker)
Write-Host "`n📦 Levantando microservicios de IA (Docker)..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al iniciar Docker Compose. Asegúrate de que Docker Desktop esté corriendo." -ForegroundColor Red
    exit
}

# 3. Esperar a que los servicios estén listos (Opcional, pero recomendado)
Write-Host "⏳ Esperando a que los servicios se estabilicen (10s)..."
Start-Sleep -Seconds 10

# 4. Iniciar Orquestador Local
Write-Host "`n🎙️ Iniciando Orquestador de Voz..." -ForegroundColor Green

# Verificar dependencias
if (Test-Path "orchestrator/requirements.txt") {
    Write-Host "Verificando dependencias de Python..."
    pip install -q -r orchestrator/requirements.txt
}

# Ejecutar el orquestador en una nueva ventana para mantener los logs visibles
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python orchestrator/main.py"

Write-Host "`n✅ ¡Sistema en marcha!" -ForegroundColor Cyan
Write-Host "Accede al Dashboard en: http://localhost"
Write-Host "Accede a la API de Gestión en: http://localhost:8080"
Write-Host "`nPuedes cerrar esta ventana. El orquestador seguirá corriendo en la nueva terminal."
