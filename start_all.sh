#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Starting all services ==="

for svc in django_microservice fastapi_microservice litestar_microservice robyn_microservice; do
    echo ""
    echo "--- $svc ---"
    cd "$ROOT/$svc"
    docker-compose up -d --build
done

echo ""
echo "=== All services started ==="
echo ""
echo "  Django:   http://localhost:8000/api/users/"
echo "  FastAPI:  http://localhost:8001/api/users/"
echo "  Litestar: http://localhost:8002/api/users/"
echo "  Robyn:    http://localhost:8003/api/users/"
echo ""
echo "Seed Django:"
echo "  cd django_microservice && docker-compose exec api python manage.py seed_db"
