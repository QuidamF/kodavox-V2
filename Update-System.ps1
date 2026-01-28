Write-Host "Updating KodaVox Services..." -ForegroundColor Cyan

# Force rebuild of services to pick up code changes
docker-compose up -d --build

Write-Host "Update Complete! System is running." -ForegroundColor Green
Write-Host "You can now say 'Alexa'..." -ForegroundColor Yellow
