"""
Fair benchmark: each framework tested in isolation.
5 endpoint types, 3 runs per framework, median taken.
"""
import asyncio
import json
import os
import subprocess
import time
import statistics
import httpx

ROOT = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    ("Django",   "django_microservice",   8000),
    ("FastAPI",  "fastapi_microservice",  8001),
    ("Litestar", "litestar_microservice", 8002),
    ("Robyn",    "robyn_microservice",    8003),
]

DB_SEEDS = {
    "django_microservice":   "postgresql://app:app@localhost:5433/app",
    "fastapi_microservice":  "postgresql://postgres:postgres@localhost:5436/fastapi_db",
    "litestar_microservice": "postgresql://postgres:postgres@localhost:5434/litestar_db",
    "robyn_microservice":    "postgresql://postgres:postgres@localhost:5435/robyn_db",
}

N_LATENCY = 100
N_THROUGHPUT = 300
CONCURRENCY = 20
N_WARMUP = 10
N_RUNS = 3


def run_cmd(cmd, cwd=None):
    subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True)


def stop_all():
    for _, svc_dir, _ in SERVICES:
        run_cmd("docker compose down -v", cwd=os.path.join(ROOT, svc_dir))


def start_service(svc_dir):
    run_cmd("docker compose up -d --build", cwd=os.path.join(ROOT, svc_dir))


def stop_service(svc_dir):
    run_cmd("docker compose down -v", cwd=os.path.join(ROOT, svc_dir))


def wait_for_service(port, timeout=90):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/api/users/", timeout=5)
            return True
        except Exception:
            time.sleep(1)
    return False


def seed_db(svc_dir):
    import random
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("    psycopg not installed, skipping seed")
        return

    dsn = DB_SEEDS[svc_dir]
    random.seed(42)
    users = [{"email": f"user{i}@test.com", "name": f"User {i}"} for i in range(1000)]
    orders = []
    for uid in range(1000):
        for _ in range(random.randint(5, 10)):
            orders.append({"user_idx": uid, "total_price": round(random.uniform(10, 500), 2)})

    conn = psycopg.connect(dsn, row_factory=dict_row)
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('users','app_user')"
    ).fetchall()
    table_names = {t["table_name"] for t in tables}
    is_django = "app_user" in table_names

    if is_django:
        ut, ot = "app_user", "app_order"
    else:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, total_price NUMERIC(12,2) NOT NULL)")
        conn.commit()
        ut, ot = "users", "orders"

    conn.execute(f"DELETE FROM {ot}")
    conn.execute(f"DELETE FROM {ut}")
    conn.execute(f"ALTER SEQUENCE {ut}_id_seq RESTART WITH 1")
    conn.execute(f"ALTER SEQUENCE {ot}_id_seq RESTART WITH 1")
    conn.commit()

    with conn.cursor() as cur:
        with cur.copy(f"COPY {ut} (email, name) FROM STDIN") as copy:
            for u in users:
                copy.write_row((u["email"], u["name"]))
    conn.commit()

    user_ids = [r["id"] for r in conn.execute(f"SELECT id FROM {ut} ORDER BY id").fetchall()]

    if is_django:
        with conn.cursor() as cur:
            with cur.copy(f"COPY {ot} (user_id, total_price, created_at) FROM STDIN") as copy:
                for o in orders:
                    copy.write_row((user_ids[o["user_idx"]], o["total_price"], "2026-01-01 00:00:00+00"))
    else:
        with conn.cursor() as cur:
            with cur.copy(f"COPY {ot} (user_id, total_price) FROM STDIN") as copy:
                for o in orders:
                    copy.write_row((user_ids[o["user_idx"]], o["total_price"]))
    conn.commit()
    total = conn.execute(f"SELECT count(*) as c FROM {ot}").fetchone()["c"]
    conn.close()
    print(f"    Seeded: 1000 users, {total} orders")


async def warmup(port, n=N_WARMUP):
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(n):
            try:
                await client.get(f"http://localhost:{port}/api/users/")
            except Exception:
                pass


async def latency_test(port, path, n=N_LATENCY):
    latencies = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(n):
            try:
                start = time.perf_counter()
                r = await client.get(f"http://localhost:{port}{path}")
                elapsed = (time.perf_counter() - start) * 1000
                if r.status_code == 200:
                    latencies.append(elapsed)
            except Exception:
                pass
    if not latencies:
        return {"avg": 0, "p50": 0, "p95": 0, "p99": 0, "ok": 0}
    s = sorted(latencies)
    n = len(s)
    return {
        "avg": round(statistics.mean(s), 2),
        "p50": round(statistics.median(s), 2),
        "p95": round(s[int(0.95 * (n - 1))], 2),
        "p99": round(s[int(0.99 * (n - 1))], 2),
        "ok": n,
    }


async def throughput_test(port, path, n=N_THROUGHPUT):
    sem = asyncio.Semaphore(CONCURRENCY)
    ok = fail = 0
    timeout = httpx.Timeout(connect=5, read=30, write=5, pool=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def one():
            nonlocal ok, fail
            async with sem:
                try:
                    r = await client.get(f"http://localhost:{port}{path}")
                    if r.status_code == 200:
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
        start = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(n)))
        elapsed = time.perf_counter() - start
    return {"ok": ok, "fail": fail, "elapsed_s": round(elapsed, 2), "rps": round(ok / elapsed, 2) if elapsed else 0}


async def post_latency(port, n=50):
    latencies = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(n):
            try:
                payload = {"email": f"pl_{port}_{int(time.time()*1000)}_{i}@b.com", "name": f"P{i}"}
                start = time.perf_counter()
                r = await client.post(f"http://localhost:{port}/api/users/", json=payload)
                elapsed = (time.perf_counter() - start) * 1000
                if r.status_code in (200, 201):
                    latencies.append(elapsed)
            except Exception:
                pass
    if not latencies:
        return {"avg": 0, "p50": 0, "p95": 0, "ok": 0}
    s = sorted(latencies)
    n = len(s)
    return {
        "avg": round(statistics.mean(s), 2),
        "p50": round(statistics.median(s), 2),
        "p95": round(s[int(0.95 * (n - 1))], 2),
        "ok": n,
    }


async def post_throughput(port, n=200):
    sem = asyncio.Semaphore(CONCURRENCY)
    ok = fail = 0
    timeout = httpx.Timeout(connect=5, read=30, write=5, pool=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def one(i):
            nonlocal ok, fail
            async with sem:
                try:
                    payload = {"email": f"pt_{port}_{int(time.time()*1000)}_{i}@b.com", "name": f"T{i}"}
                    r = await client.post(f"http://localhost:{port}/api/users/", json=payload)
                    if r.status_code in (200, 201):
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
        start = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(n)))
        elapsed = time.perf_counter() - start
    return {"ok": ok, "fail": fail, "elapsed_s": round(elapsed, 2), "rps": round(ok / elapsed, 2) if elapsed else 0}


ENDPOINTS = [
    ("GET /api/users/",            "/api/users/"),
    ("GET /api/users/optimized/",  "/api/users/optimized/"),
    ("GET /api/users/?page&size",  "/api/users/?page=1&size=50"),
    ("GET /api/analytics/",        "/api/analytics/"),
]


async def bench_one_run(port):
    await warmup(port)
    results = {}

    for label, path in ENDPOINTS:
        lat = await latency_test(port, path)
        await asyncio.sleep(1)
        thr = await throughput_test(port, path)
        await asyncio.sleep(2)
        results[label] = {"latency": lat, "throughput": thr}

    # POST
    await warmup(port, n=3)
    pl = await post_latency(port)
    await asyncio.sleep(1)
    pt = await post_throughput(port)
    results["POST /api/users/"] = {"latency": pl, "throughput": pt}

    return results


async def main():
    print("=" * 60)
    print("  BENCHMARK — 5 endpoints, isolated, 3 runs median")
    print(f"  Latency: {N_LATENCY} req | Throughput: {N_THROUGHPUT} req (c={CONCURRENCY})")
    print("=" * 60)

    stop_all()
    time.sleep(3)

    all_results = {}

    for name, svc_dir, port in SERVICES:
        print(f"\n{'='*60}")
        print(f"  {name} (port {port})")
        print(f"{'='*60}")

        print(f"  Starting...")
        start_service(svc_dir)
        if not wait_for_service(port):
            print(f"  FAILED!")
            stop_service(svc_dir)
            continue

        print(f"  Seeding...")
        seed_db(svc_dir)

        runs = []
        for run_i in range(N_RUNS):
            print(f"  Run {run_i + 1}/{N_RUNS}...")
            result = await bench_one_run(port)
            runs.append(result)
            for label in result:
                lat = result[label]["latency"]
                thr = result[label]["throughput"]
                print(f"    {label}: avg={lat['avg']}ms | {thr['rps']} RPS")

        # Median by GET /api/users/ avg latency
        runs_sorted = sorted(runs, key=lambda r: r["GET /api/users/"]["latency"]["avg"])
        median_run = runs_sorted[len(runs_sorted) // 2]
        all_results[name] = {"median_run": median_run, "all_runs": runs}

        print(f"  Stopping...")
        stop_service(svc_dir)
        time.sleep(10)  # wait for ports to release

    # Summary
    print(f"\n{'='*60}")
    print("  FINAL RESULTS (median of 3 runs)")
    print(f"{'='*60}")

    for label in [e[0] for e in ENDPOINTS] + ["POST /api/users/"]:
        print(f"\n  {label}")
        print(f"  {'Framework':<12} {'Avg':>8} {'P50':>8} {'P95':>8} | {'RPS':>8}")
        for name in [n for n, _, _ in SERVICES]:
            if name not in all_results:
                continue
            d = all_results[name]["median_run"][label]
            lat, thr = d["latency"], d["throughput"]
            print(f"  {name:<12} {lat['avg']:>7.1f}ms {lat['p50']:>7.1f}ms {lat.get('p95',0):>7.1f}ms | {thr['rps']:>7.1f}")

    # Save
    output = {}
    for name, data in all_results.items():
        output[name] = {}
        for label in data["median_run"]:
            output[name][label] = data["median_run"][label]
        output[name]["all_runs_baseline_avg"] = [
            r["GET /api/users/"]["latency"]["avg"] for r in data["all_runs"]
        ]
    with open(os.path.join(ROOT, "benchmark_results.json"), "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to benchmark_results.json")


if __name__ == "__main__":
    asyncio.run(main())
