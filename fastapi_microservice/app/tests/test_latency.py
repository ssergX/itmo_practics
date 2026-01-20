import json
import statistics
import time
import pytest
import httpx

BASE_URL = "http://localhost:8001"
OUT_FILE = "latency_users_fastapi.json"


@pytest.mark.asyncio
async def test_average_latency_users():
    latencies = []
    n = 50

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        for _ in range(n):
            start = time.perf_counter()
            r = await client.get("/api/users/")
            elapsed = (time.perf_counter() - start) * 1000
            assert r.status_code == 200
            latencies.append(elapsed)

    lat_sorted = sorted(latencies)
    result = {
        "endpoint": "/api/users/",
        "requests": n,
        "avg_ms": round(statistics.mean(latencies), 2),
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(lat_sorted[int(0.95 * (n - 1))], 2),
        "p99_ms": round(lat_sorted[int(0.99 * (n - 1))], 2),
        "samples_ms": [round(x, 2) for x in latencies],
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    assert result["avg_ms"] < 3000
