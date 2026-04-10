$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Starting all services ===" -ForegroundColor Cyan

$services = @("django_microservice", "fastapi_microservice", "litestar_microservice", "robyn_microservice")

foreach ($svc in $services) {
    Write-Host ""
    Write-Host "--- $svc ---" -ForegroundColor Yellow
    Push-Location "$root\$svc"
    docker-compose up -d --build
    Pop-Location
}

Write-Host ""
Write-Host "=== All services started ===" -ForegroundColor Green
Write-Host ""
Write-Host "  Django:   http://localhost:8000/api/users/"
Write-Host "  FastAPI:  http://localhost:8001/api/users/"
Write-Host "  Litestar: http://localhost:8002/api/users/"
Write-Host "  Robyn:    http://localhost:8003/api/users/"
Write-Host ""
Write-Host "Seed Django:"
Write-Host "  cd django_microservice; docker-compose exec api python manage.py seed_db"
