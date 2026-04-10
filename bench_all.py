"""
Fair benchmark: each framework tested in isolation.
1. Stop all services
2. For each framework:
   a. Start only this service
   b. Seed DB
   c. Warmup (10 requests, discarded)
   d. Latency: 200 sequential GET, 100 sequential POST
   e. Throughput: 500 concurrent GET, 500 concurrent POST (concurrency=20)
   f. 3 runs, take median
   g. Stop service
3. Save results
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

# DB connection strings for seeding
DB_SEEDS = {
    "django_microservice":   "postgresql://app:app@localhost:5433/app",
    "fastapi_microservice":  "postgresql://postgres:postgres@localhost:5436/fastapi_db",
    "litestar_microservice": "postgresql://postgres:postgres@localhost:5434/litestar_db",
    "robyn_microservice":    "postgresql://postgres:postgres@localhost:5435/robyn_db",
}

N_LATENCY_GET = 200
N_LATENCY_POST = 100
N_THROUGHPUT = 500
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
    """Seed single DB using psycopg."""
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

    # Detect table names
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('users','app_user')"
    ).fetchall()
    table_names = {t["table_name"] for t in tables}

    is_django = "app_user" in table_names
    if is_django:
        ut, ot = "app_user", "app_order"
    else:
        # Ensure tables exist
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
            await client.get(f"http://localhost:{port}/api/users/")


async def latency_get(port, n=N_LATENCY_GET):
    latencies = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(n):
            try:
                start = time.perf_counter()
                r = await client.get(f"http://localhost:{port}/api/users/")
                elapsed = (time.perf_counter() - start) * 1000
                if r.status_code == 200:
                    latencies.append(elapsed)
            except Exception:
                pass
    s = sorted(latencies)
    n = len(s)
    return {
        "avg": round(statistics.mean(s), 2),
        "p50": round(statistics.median(s), 2),
        "p95": round(s[int(0.95 * (n - 1))], 2),
        "p99": round(s[int(0.99 * (n - 1))], 2),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
        "ok": n,
    }


async def latency_post(port, n=N_LATENCY_POST):
    latencies = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(n):
            payload = {"email": f"post_{port}_{int(time.time()*1000)}_{i}@b.com", "name": f"P{i}"}
            try:
                start = time.perf_counter()
                r = await client.post(f"http://localhost:{port}/api/users/", json=payload)
                elapsed = (time.perf_counter() - start) * 1000
                if r.status_code in (200, 201):
                    latencies.append(elapsed)
            except Exception:
                pass
    s = sorted(latencies)
    n = len(s)
    if n == 0:
        return None
    return {
        "avg": round(statistics.mean(s), 2),
        "p50": round(statistics.median(s), 2),
        "p95": round(s[int(0.95 * (n - 1))], 2),
        "p99": round(s[int(0.99 * (n - 1))], 2),
        "ok": n,
    }


async def throughput_get(port, n=N_THROUGHPUT):
    sem = asyncio.Semaphore(CONCURRENCY)
    ok = fail = 0
    timeout = httpx.Timeout(connect=5, read=30, write=5, pool=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def one():
            nonlocal ok, fail
            async with sem:
                try:
                    r = await client.get(f"http://localhost:{port}/api/users/")
                    if r.status_code == 200:
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
        start = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(n)))
        elapsed = time.perf_counter() - start
    return {"ok": ok, "fail": fail, "elapsed_s": round(elapsed, 2), "rps": round(ok / elapsed, 2)}


async def throughput_post(port, n=N_THROUGHPUT):
    sem = asyncio.Semaphore(CONCURRENCY)
    ok = fail = 0
    timeout = httpx.Timeout(connect=5, read=30, write=5, pool=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def one(i):
            nonlocal ok, fail
            async with sem:
                try:
                    payload = {"email": f"thr_{port}_{int(time.time()*1000)}_{i}@b.com", "name": f"T{i}"}
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
    return {"ok": ok, "fail": fail, "elapsed_s": round(elapsed, 2), "rps": round(ok / elapsed, 2)}


async def bench_one_run(port):
    """Single benchmark run for one service."""
    await warmup(port)
    gl = await latency_get(port)
    await asyncio.sleep(2)  # cooldown between tests
    gt = await throughput_get(port)
    await asyncio.sleep(3)  # cooldown after heavy throughput
    await warmup(port, n=3)  # re-warmup after throughput
    pl = await latency_post(port)
    await asyncio.sleep(2)
    pt = await throughput_post(port)
    return {"get_latency": gl, "get_throughput": gt, "post_latency": pl, "post_throughput": pt}


async def main():
    print("=" * 60)
    print("  FAIR BENCHMARK — isolated, with warmup, 3 runs median")
    print(f"  GET latency: {N_LATENCY_GET} req | POST latency: {N_LATENCY_POST} req")
    print(f"  Throughput: {N_THROUGHPUT} req, concurrency={CONCURRENCY}")
    print(f"  Runs: {N_RUNS} (median taken)")
    print("=" * 60)

    print("\nStopping all services...")
    stop_all()
    time.sleep(3)

    all_results = {}

    for name, svc_dir, port in SERVICES:
        print(f"\n{'='*60}")
        print(f"  {name} (port {port})")
        print(f"{'='*60}")

        print(f"  Starting {name}...")
        start_service(svc_dir)

        print(f"  Waiting for service...")
        if not wait_for_service(port):
            print(f"  FAILED to start {name}!")
            stop_service(svc_dir)
            continue

        print(f"  Seeding DB...")
        seed_db(svc_dir)

        runs = []
        for run_i in range(N_RUNS):
            print(f"  Run {run_i + 1}/{N_RUNS}...")
            result = await bench_one_run(port)
            runs.append(result)
            gl = result["get_latency"]
            gt = result["get_throughput"]
            print(f"    GET: avg={gl['avg']}ms p50={gl['p50']}ms p95={gl['p95']}ms | {gt['rps']} RPS")
            pl = result["post_latency"]
            pt = result["post_throughput"]
            if pl:
                print(f"    POST: avg={pl['avg']}ms p50={pl['p50']}ms | {pt['rps']} RPS")

        # Take median of 3 runs by GET avg latency
        runs_sorted = sorted(runs, key=lambda r: r["get_latency"]["avg"])
        median_run = runs_sorted[len(runs_sorted) // 2]

        all_results[name] = {
            "median_run": median_run,
            "all_runs": runs,
        }

        print(f"\n  Stopping {name}...")
        stop_service(svc_dir)
        time.sleep(3)

    # Summary
    print(f"\n{'='*60}")
    print("  FINAL RESULTS (median of 3 runs)")
    print(f"{'='*60}")

    print(f"\n  GET /api/users/ — Latency ({N_LATENCY_GET} sequential)")
    print(f"  {'Framework':<12} {'Avg':>8} {'P50':>8} {'P95':>8} {'P99':>8}")
    for name in [n for n, _, _ in SERVICES]:
        if name not in all_results:
            continue
        gl = all_results[name]["median_run"]["get_latency"]
        print(f"  {name:<12} {gl['avg']:>7.1f}ms {gl['p50']:>7.1f}ms {gl['p95']:>7.1f}ms {gl['p99']:>7.1f}ms")

    print(f"\n  GET /api/users/ — Throughput ({N_THROUGHPUT} req, concurrency={CONCURRENCY})")
    print(f"  {'Framework':<12} {'RPS':>8} {'OK':>6} {'Fail':>6} {'Time':>8}")
    for name in [n for n, _, _ in SERVICES]:
        if name not in all_results:
            continue
        gt = all_results[name]["median_run"]["get_throughput"]
        print(f"  {name:<12} {gt['rps']:>7.1f} {gt['ok']:>6} {gt['fail']:>6} {gt['elapsed_s']:>7.1f}s")

    print(f"\n  POST /api/users/ — Latency ({N_LATENCY_POST} sequential)")
    print(f"  {'Framework':<12} {'Avg':>8} {'P50':>8} {'P95':>8} {'P99':>8}")
    for name in [n for n, _, _ in SERVICES]:
        if name not in all_results:
            continue
        pl = all_results[name]["median_run"]["post_latency"]
        if pl:
            print(f"  {name:<12} {pl['avg']:>7.1f}ms {pl['p50']:>7.1f}ms {pl['p95']:>7.1f}ms {pl['p99']:>7.1f}ms")

    print(f"\n  POST /api/users/ — Throughput ({N_THROUGHPUT} req, concurrency={CONCURRENCY})")
    print(f"  {'Framework':<12} {'RPS':>8} {'OK':>6} {'Fail':>6} {'Time':>8}")
    for name in [n for n, _, _ in SERVICES]:
        if name not in all_results:
            continue
        pt = all_results[name]["median_run"]["post_throughput"]
        print(f"  {name:<12} {pt['rps']:>7.1f} {pt['ok']:>6} {pt['fail']:>6} {pt['elapsed_s']:>7.1f}s")

    # Save
    output = {
        name: {
            "get_latency": data["median_run"]["get_latency"],
            "get_throughput": data["median_run"]["get_throughput"],
            "post_latency": data["median_run"]["post_latency"],
            "post_throughput": data["median_run"]["post_throughput"],
            "all_runs_get_avg": [r["get_latency"]["avg"] for r in data["all_runs"]],
        }
        for name, data in all_results.items()
    }
    with open(os.path.join(ROOT, "benchmark_results.json"), "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to benchmark_results.json")


if __name__ == "__main__":
    asyncio.run(main())
