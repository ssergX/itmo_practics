import asyncio
import json
import time
import pytest
import httpx

BASE_URL = "http://localhost:8002"
OUT_FILE = "throughput_users_litestar.json"


@pytest.mark.asyncio
async def test_users_throughput():
    concurrency = 20
    total_requests = 200

    timeout = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=30.0)
    sem = asyncio.Semaphore(concurrency)

    ok = 0
    fail = 0

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:

        async def one():
            nonlocal ok, fail
            async with sem:
                try:
                    r = await client.get("/api/users/")
                    if r.status_code == 200:
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1

        start = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(total_requests)))
        elapsed = time.perf_counter() - start

    rps = ok / elapsed if elapsed else 0.0
    result = {
        "endpoint": "/api/users/",
        "total_requests": total_requests,
        "concurrency": concurrency,
        "ok": ok,
        "fail": fail,
        "elapsed_s": round(elapsed, 3),
        "throughput_rps": round(rps, 2),
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    assert ok > 0
