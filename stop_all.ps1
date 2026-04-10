$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Stopping all services ===" -ForegroundColor Cyan

$services = @("django_microservice", "fastapi_microservice", "litestar_microservice", "robyn_microservice")

foreach ($svc in $services) {
    Write-Host "--- $svc ---" -ForegroundColor Yellow
    Push-Location "$root\$svc"
    docker-compose down
    Pop-Location
}

Write-Host ""
Write-Host "=== All services stopped ===" -ForegroundColor Green
