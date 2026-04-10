import time
import django
from django.db import connection
from django.http import JsonResponse

_start_time = time.time()


def health_check(request):
    db_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return JsonResponse({
        "status": "ok" if db_ok else "degraded",
        "service": "django",
        "framework": f"Django {django.get_version()}",
        "database": "connected" if db_ok else "disconnected",
        "uptime_s": round(time.time() - _start_time, 1),
    })
