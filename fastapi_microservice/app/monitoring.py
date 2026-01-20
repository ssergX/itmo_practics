import time
import logging
import psutil

logger = logging.getLogger("monitoring")
_process = psutil.Process()


def snapshot(start_perf: float) -> dict:
    elapsed_ms = (time.perf_counter() - start_perf) * 1000
    cpu = _process.cpu_percent(interval=None)  # может быть 0.0 на коротких запросах — это ок
    ram_mb = _process.memory_info().rss / (1024 * 1024)
    threads = _process.num_threads()
    return {
        "elapsed_ms": round(elapsed_ms, 2),
        "cpu_percent": cpu,
        "ram_mb": round(ram_mb, 1),
        "threads": threads,
    }


def log_line(method: str, path: str, m: dict):
    logger.info(
        "%s %s | time=%sms | cpu=%s%% | ram=%sMB | threads=%s",
        method, path, m["elapsed_ms"], m["cpu_percent"], m["ram_mb"], m["threads"]
    )
