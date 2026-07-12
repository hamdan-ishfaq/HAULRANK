"""Request tracing middleware — one line per HTTP request for Render logs."""

from __future__ import annotations

import logging
import time
import uuid

logger = logging.getLogger("haulrank.request")


class RequestTraceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.request_id = request_id
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response["X-Request-ID"] = request_id
        logger.info(
            "rid=%s method=%s path=%s status=%s ms=%.1f origin=%s",
            request_id,
            request.method,
            request.get_full_path(),
            response.status_code,
            elapsed_ms,
            request.headers.get("Origin", "-"),
        )
        return response
