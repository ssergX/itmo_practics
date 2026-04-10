"""
Full benchmark: GET latency, GET throughput, POST latency, POST throughput.
All 4 frameworks, identical parameters.
"""
import asyncio
import json
import time
import statistics
import httpx

SERVICES = [
    ("Django",   8000),
    ("FastAPI",  8001),
    ("Litestar", 8002),
    ("Robyn",    8003),
]

N_LATENCY = 50
N_THROUGHPUT = 200
CONCURRENCY = 20


async def latency_get(name, port):
    latencies = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(N_LATENCY):
            start = time.perf_counter()
            r = await client.get(f"http://localhost:{port}/api/users/")
            elapsed = (time.perf_counter() - start) * 1000
            if r.status_code == 200:
                latencies.append(elapsed)
    s = sorted(latencies)
    n = len(s)
    return {
        "test": "GET_latency", "service": name,
        "avg": round(statistics.mean(s), 2),
        "p50": round(statistics.median(s), 2),
        "p95": round(s[int(0.95 * (n - 1))], 2),
        "p99": round(s[int(0.99 * (n - 1))], 2),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
        "ok": n,
    }


async def throughput_get(name, port):
    sem = asyncio.Semaphore(CONCURRENCY)
    ok = fail = 0
    timeout = httpx.Timeout(connect=5, read=30, write=5, pool=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def one():
            nonlocal ok, fail
            async with sem:
                try:
                    r = await client.get(f"http://localhost:{port}/api/users/")
                    ok += 1 if r.status_code == 200 else 0
                    fail += 0 if r.status_code == 200 else 1
                except:
                    fail += 1
        start = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(N_THROUGHPUT)))
        elapsed = time.perf_counter() - start
    return {
        "test": "GET_throughput", "service": name,
        "ok": ok, "fail": fail,
        "elapsed_s": round(elapsed, 2),
        "rps": round(ok / elapsed, 2),
    }


async def latency_post(name, port):
    latencies = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(N_LATENCY):
            payload = {"email": f"post_lat_{port}_{i}@bench.com", "name": f"PLat {i}"}
            start = time.perf_counter()
            r = await client.post(f"http://localhost:{port}/api/users/", json=payload)
            elapsed = (time.perf_counter() - start) * 1000
            if r.status_code in (200, 201):
                latencies.append(elapsed)
    s = sorted(latencies)
    n = len(s)
    if n == 0:
        return {"test": "POST_latency", "service": name, "error": "all failed"}
    return {
        "test": "POST_latency", "service": name,
        "avg": round(statistics.mean(s), 2),
        "p50": round(statistics.median(s), 2),
        "p95": round(s[int(0.95 * (n - 1))], 2),
        "p99": round(s[int(0.99 * (n - 1))], 2),
        "ok": n,
    }


async def throughput_post(name, port):
    sem = asyncio.Semaphore(CONCURRENCY)
    ok = fail = 0
    timeout = httpx.Timeout(connect=5, read=30, write=5, pool=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def one(i):
            nonlocal ok, fail
            async with sem:
                try:
                    payload = {"email": f"post_thr_{port}_{i}@bench.com", "name": f"PThr {i}"}
                    r = await client.post(f"http://localhost:{port}/api/users/", json=payload)
                    ok += 1 if r.status_code in (200, 201) else 0
                    fail += 0 if r.status_code in (200, 201) else 1
                except:
                    fail += 1
        start = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(N_THROUGHPUT)))
        elapsed = time.perf_counter() - start
    return {
        "test": "POST_throughput", "service": name,
        "ok": ok, "fail": fail,
        "elapsed_s": round(elapsed, 2),
        "rps": round(ok / elapsed, 2),
    }


async def main():
    results = []

    print("=" * 60)
    print("GET /api/users/ — LATENCY (50 sequential)")
    print("=" * 60)
    for name, port in SERVICES:
        r = await latency_get(name, port)
        results.append(r)
        print(f"  {name:10s}: avg={r['avg']:>7.2f}  p50={r['p50']:>7.2f}  p95={r['p95']:>7.2f}  p99={r['p99']:>7.2f}ms")

    print()
    print("=" * 60)
    print("GET /api/users/ — THROUGHPUT (200 req, concurrency=20)")
    print("=" * 60)
    for name, port in SERVICES:
        r = await throughput_get(name, port)
        results.append(r)
        print(f"  {name:10s}: {r['ok']}/{r['ok']+r['fail']} ok  {r['elapsed_s']}s  {r['rps']} RPS")

    print()
    print("=" * 60)
    print("POST /api/users/ — LATENCY (50 sequential)")
    print("=" * 60)
    for name, port in SERVICES:
        r = await latency_post(name, port)
        results.append(r)
        if "error" in r:
            print(f"  {name:10s}: FAILED")
        else:
            print(f"  {name:10s}: avg={r['avg']:>7.2f}  p50={r['p50']:>7.2f}  p95={r['p95']:>7.2f}  p99={r['p99']:>7.2f}ms")

    print()
    print("=" * 60)
    print("POST /api/users/ — THROUGHPUT (200 req, concurrency=20)")
    print("=" * 60)
    for name, port in SERVICES:
        r = await throughput_post(name, port)
        results.append(r)
        print(f"  {name:10s}: {r['ok']}/{r['ok']+r['fail']} ok  {r['elapsed_s']}s  {r['rps']} RPS")

    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to benchmark_results.json")


if __name__ == "__main__":
    asyncio.run(main())
