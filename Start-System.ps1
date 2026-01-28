# Start-System.ps1
# Script para iniciar el ecosistema de KodaVox en un solo paso.

Write-Host "Iniciando KodaVox Ecosystem..." -ForegroundColor Cyan

# 1. Verificar .env
if (-not (Test-Path ".env")) {
    Write-Host "Error: No se encontro el archivo .env en la raiz." -ForegroundColor Red
    Write-Host "Por favor, crea uno basado en .env.example antes de continuar."
    exit
}

# 2. Levantar Microservicios (Docker)
Write-Host "`nLevantando microservicios de IA (Docker)..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error al iniciar Docker Compose. Asegurate de que Docker Desktop este corriendo." -ForegroundColor Red
    exit
}

# 3. Esperar a que los servicios esten listos (Opcional, pero recomendado)
Write-Host "Esperando a que los servicios se estabilicen (10s)..."
Start-Sleep -Seconds 10

# 4. Iniciar Orquestador Local
Write-Host "`nIniciando Orquestador de Voz..." -ForegroundColor Green

# Verificar dependencias
if (Test-Path "orchestrator/requirements.txt") {
    Write-Host "Verificando dependencias de Python..."
    py -3.13 -m pip install -q -r orchestrator/requirements.txt
}

# Ejecutar el orquestador en una nueva ventana para mantener los logs visibles
Start-Process powershell -ArgumentList "-NoExit", "-Command", "py -3.13 orchestrator/main.py"

Write-Host "`nSistema en marcha!" -ForegroundColor Cyan
Write-Host "Accede al Dashboard en: http://localhost"
Write-Host "Accede a la API de Gestion en: http://localhost:8080"
Write-Host ""
Write-Host "Puedes cerrar esta ventana. El orquestador seguira corriendo en la nueva terminal."
