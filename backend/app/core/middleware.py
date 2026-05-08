"""Middleware: tenant context, CORS, request ID, logging."""

from __future__ import annotations

import structlog
import uuid
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique ``X-Request-ID`` header into every request/response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # Store on request state for downstream access
        request.state.request_id = request_id

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration.

    Also records Prometheus HTTP metrics for dashboard and alerting.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import time
        from app.core.metrics import (
            HTTP_REQUEST_DURATION_SECONDS,
            HTTP_REQUESTS_IN_PROGRESS,
        )

        # Skip metrics collection for /health, /ready, /metrics
        path = request.url.path
        skip_metrics = path in ("/health", "/ready", "/metrics")

        if not skip_metrics:
            HTTP_REQUESTS_IN_PROGRESS.inc()

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        duration_ms = duration * 1000

        if not skip_metrics:
            HTTP_REQUESTS_IN_PROGRESS.dec()
            # Normalize path: strip UUIDs to keep cardinality low
            path_template = _normalize_path(path)
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                path_template=path_template,
                status_code=str(response.status_code),
            ).observe(duration)

        logger.info(
            "http_request",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response


# UUID pattern: 8-4-4-4-12 hex digits
import re
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _normalize_path(path: str) -> str:
    """Replace UUIDs and numeric IDs with placeholders to keep metric cardinality low."""
    normalized = _UUID_RE.sub("{id}", path)
    # Also replace pure numeric path segments
    parts = normalized.split("/")
    parts = ["{id}" if p.isdigit() else p for p in parts]
    return "/".join(parts)


def setup_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID injection
    app.add_middleware(RequestIDMiddleware)

    # Access logging
    app.add_middleware(AccessLogMiddleware)
