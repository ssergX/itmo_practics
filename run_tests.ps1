$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$results = "$root\results"
New-Item -ItemType Directory -Force -Path $results | Out-Null

Write-Host "=== Running benchmarks ===" -ForegroundColor Cyan

# Django
Write-Host "`n--- Django: latency ---" -ForegroundColor Yellow
Push-Location "$root\django_microservice"
pytest tests/test_latency.py -v --tb=short 2>&1 | Tee-Object "$results\django_latency.log"

Write-Host "`n--- Django: throughput ---" -ForegroundColor Yellow
pytest tests/test_throughput.py -v --tb=short 2>&1 | Tee-Object "$results\django_throughput.log"
Pop-Location

# FastAPI
Write-Host "`n--- FastAPI: latency ---" -ForegroundColor Yellow
Push-Location "$root\fastapi_microservice"
pytest app/tests/test_latency.py -v --tb=short 2>&1 | Tee-Object "$results\fastapi_latency.log"

Write-Host "`n--- FastAPI: throughput ---" -ForegroundColor Yellow
pytest app/tests/test_throughput.py -v --tb=short 2>&1 | Tee-Object "$results\fastapi_throughput.log"
Pop-Location

# Litestar
Write-Host "`n--- Litestar: latency ---" -ForegroundColor Yellow
Push-Location "$root\litestar_microservice"
pytest app/tests/test_latency.py -v --tb=short 2>&1 | Tee-Object "$results\litestar_latency.log"

Write-Host "`n--- Litestar: throughput ---" -ForegroundColor Yellow
pytest app/tests/test_throughput.py -v --tb=short 2>&1 | Tee-Object "$results\litestar_throughput.log"
Pop-Location

# Robyn
Write-Host "`n--- Robyn: latency ---" -ForegroundColor Yellow
Push-Location "$root\robyn_microservice"
pytest app/tests/test_latency.py -v --tb=short 2>&1 | Tee-Object "$results\robyn_latency.log"

Write-Host "`n--- Robyn: throughput ---" -ForegroundColor Yellow
pytest app/tests/test_throughput.py -v --tb=short 2>&1 | Tee-Object "$results\robyn_throughput.log"
Pop-Location

Write-Host "`n=== Done. Results in $results\ ===" -ForegroundColor Green
