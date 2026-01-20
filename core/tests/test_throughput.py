import time
import json
import asyncio
from pathlib import Path

import httpx
import pytest

BASE_URL = "http://localhost:8000"
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


@pytest.mark.asyncio
async def test_users_throughput():
    concurrency = 20
    total_requests = 100

    timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0, )
    success, failed = 0, 0

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout, ) as client:
        async def fetch():
            nonlocal success, failed
            try:
                response = await client.get("/api/users/")
                if response.status_code == 200:
                    success += 1
                else:
                    failed += 1
            except httpx.ReadTimeout:
                failed += 1
            except Exception:
                failed += 1

        start_time = time.perf_counter()

        tasks = []
        for _ in range(total_requests):
            tasks.append(fetch())
            if len(tasks) == concurrency:
                await asyncio.gather(*tasks)
                tasks.clear()

        if tasks:
            await asyncio.gather(*tasks)

        total_time = time.perf_counter() - start_time
    throughput = success / total_time if total_time > 0 else 0
    result = {
        "endpoint": "/api/users/",
        "total_requests": total_requests,
        "concurrency": concurrency,
        "success": success,
        "failed": failed,
        "total_time_sec": round(total_time, 2),
        "throughput_rps": round(throughput, 2),
    }

    with open(RESULTS_DIR / "throughput_users.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))

    assert success > 0
