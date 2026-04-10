import time
import uuid
import json
import logging

logger = logging.getLogger("app.requests")


class StructuredLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.request_id = request_id
        start = time.perf_counter()

        response = self.get_response(request)

        elapsed = (time.perf_counter() - start) * 1000
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "service": "django",
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "elapsed_ms": round(elapsed, 2),
        }
        logger.info(json.dumps(log_entry, ensure_ascii=False))

        response["X-Request-ID"] = request_id
        return response
