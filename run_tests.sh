#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$ROOT/results"
mkdir -p "$RESULTS"

echo "=== Running benchmarks ==="

# Django
echo ""
echo "--- Django: latency ---"
cd "$ROOT/django_microservice"
pytest tests/test_latency.py -v --tb=short 2>&1 | tee "$RESULTS/django_latency.log"

echo ""
echo "--- Django: throughput ---"
pytest tests/test_throughput.py -v --tb=short 2>&1 | tee "$RESULTS/django_throughput.log"

# FastAPI
echo ""
echo "--- FastAPI: latency ---"
cd "$ROOT/fastapi_microservice"
pytest app/tests/test_latency.py -v --tb=short 2>&1 | tee "$RESULTS/fastapi_latency.log"

echo ""
echo "--- FastAPI: throughput ---"
pytest app/tests/test_throughput.py -v --tb=short 2>&1 | tee "$RESULTS/fastapi_throughput.log"

# Litestar
echo ""
echo "--- Litestar: latency ---"
cd "$ROOT/litestar_microservice"
pytest app/tests/test_latency.py -v --tb=short 2>&1 | tee "$RESULTS/litestar_latency.log"

echo ""
echo "--- Litestar: throughput ---"
pytest app/tests/test_throughput.py -v --tb=short 2>&1 | tee "$RESULTS/litestar_throughput.log"

# Robyn
echo ""
echo "--- Robyn: latency ---"
cd "$ROOT/robyn_microservice"
pytest app/tests/test_latency.py -v --tb=short 2>&1 | tee "$RESULTS/robyn_latency.log"

echo ""
echo "--- Robyn: throughput ---"
pytest app/tests/test_throughput.py -v --tb=short 2>&1 | tee "$RESULTS/robyn_throughput.log"

echo ""
echo "=== Done. Results in $RESULTS/ ==="
