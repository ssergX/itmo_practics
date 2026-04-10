import psutil
import os


def get_process_metrics():
    process = psutil.Process(os.getpid())

    return {
        "cpu_percent": process.cpu_percent(interval=None),
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "threads": process.num_threads(),
    }