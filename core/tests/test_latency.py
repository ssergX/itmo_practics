import time
import json
import statistics
from pathlib import Path

import httpx
import pytest

BASE_URL = "http://localhost:8000"
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


@pytest.mark.asyncio
async def test_average_latency_users():
    latencies = []
    requests_count = 50

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        for _ in range(requests_count):
            start = time.perf_counter()
            response = await client.get("/api/users/")
            elapsed = (time.perf_counter() - start) * 1000

            assert response.status_code == 200
            latencies.append(elapsed)

    # агрегаты
    avg_latency = statistics.mean(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    p95 = statistics.quantiles(latencies, n=100)[94]
    p99 = statistics.quantiles(latencies, n=100)[98]

    result = {
        "endpoint": "/api/users/",
        "requests": requests_count,
        "latency_ms": latencies,
        "avg_ms": round(avg_latency, 2),
        "min_ms": round(min_latency, 2),
        "max_ms": round(max_latency, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
    }

    output_file = RESULTS_DIR / "latency_users_baseline.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved latency results to: {output_file.resolve()}")
    print(
        f"AVG={avg_latency:.2f} ms | "
        f"P95={p95:.2f} ms | "
        f"P99={p99:.2f} ms"
    )

    assert avg_latency < 3000
