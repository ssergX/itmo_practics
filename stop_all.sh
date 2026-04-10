#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Stopping all services ==="

for svc in django_microservice fastapi_microservice litestar_microservice robyn_microservice; do
    echo "--- $svc ---"
    cd "$ROOT/$svc"
    docker-compose down
done

echo ""
echo "=== All services stopped ==="
