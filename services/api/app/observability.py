"""Request observability: request IDs, structured access logs, Prometheus metrics."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

REQUEST_COUNT = Counter(
    "smartops_api_requests_total",
    "API requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "smartops_api_request_seconds",
    "API request latency",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def _log(record: dict) -> None:
    print(json.dumps(record, default=str), file=sys.stdout, flush=True)


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or f"req-{uuid4().hex[:12]}"
        started = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - started

        route = request.scope.get("route")
        path_template = getattr(route, "path", request.url.path)

        response.headers["X-Request-Id"] = request_id
        REQUEST_COUNT.labels(request.method, path_template, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path_template).observe(elapsed)

        # Skip noisy health/metrics polling in logs.
        if path_template not in ("/health", "/metrics"):
            _log(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "service": "api",
                    "level": "info",
                    "event": "request",
                    "requestId": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "durationMs": round(elapsed * 1000, 1),
                }
            )
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
