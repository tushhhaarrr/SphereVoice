"""OpenTelemetry initialization for the SphereVoice backend.

Configures tracing and log export with OTLP HTTP exporter and
auto-instrumentation for FastAPI, SQLAlchemy, Redis, and Celery.

Both local dev and production use the same exporter: OTLP HTTP.
- Local: OTEL Collector at otel-collector:4318 → Tempo + Loki
- Production: nginx proxy on SphereVoice-production-observability:80 → /v1/* → OTEL Collector

Set OTEL_EXPORTER_OTLP_ENDPOINT to enable. Unset to disable telemetry.
"""

from __future__ import annotations

import logging

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()


def setup_opentelemetry() -> None:
    """Initialize OpenTelemetry tracing + log export with OTLP HTTP.

    Sets up the TracerProvider, log bridge, and non-FastAPI instrumentors.
    FastAPI must be instrumented separately via instrument_fastapi_app()
    after the app instance is created.
    Fails gracefully — telemetry issues must never crash the app.
    """
    settings = get_settings()

    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        logger.info("otel_disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        # ── Resource (service identity) ─────────────────────────
        resource = Resource.create(
            attributes={
                SERVICE_NAME: settings.OTEL_SERVICE_NAME,
                "deployment.environment": settings.ENVIRONMENT,
            }
        )

        provider = TracerProvider(resource=resource)

        # ── OTLP HTTP trace exporter ───────────────────────────
        # In production, nginx at port 3000 proxies /v1/* to OTEL Collector.
        # IMPORTANT: Pass full URL with path. When endpoint= is passed
        # explicitly the SDK does NOT auto-append /v1/traces — it uses
        # the value as-is. Without the path, requests go to / (Grafana).
        base = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{base}/v1/traces",
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        # ── OTLP log export (structlog → OTLP HTTP → OTEL Collector → Loki) ──
        _setup_otlp_logging(resource, f"{base}/v1/logs")

        # ── Auto-instrumentation (non-FastAPI) ──────────────────
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        SQLAlchemyInstrumentor().instrument(
            engine=None,
            enable_commenter=True,
        )
        RedisInstrumentor().instrument()
        CeleryInstrumentor().instrument()

        logger.info(
            "otel_initialized",
            exporter="otlp_http",
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            service=settings.OTEL_SERVICE_NAME,
        )
    except Exception as exc:
        logger.warning("otel_setup_failed", error=str(exc))


def instrument_fastapi_app(app) -> None:
    """Instrument an existing FastAPI app with OpenTelemetry tracing.

    Must be called AFTER setup_opentelemetry() and AFTER the app is created.
    Uses instrument_app() to inject the ASGI tracing middleware directly.
    """
    settings = get_settings()
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("fastapi_instrumented")
    except Exception as exc:
        logger.warning("fastapi_instrumentation_failed", error=str(exc))


def _setup_otlp_logging(resource, logs_endpoint: str) -> None:
    """Bridge stdlib logging → OTLP HTTP → OTEL Collector → Loki.

    Attaches an OpenTelemetry LoggingHandler to the root logger so
    every structlog message (which flows through stdlib) is also
    sent to the OTEL Collector over HTTP.  A JSON formatter ensures
    the log body in Loki is machine-parseable.

    Args:
        logs_endpoint: Full URL including path, e.g.
            http://SphereVoice-production-observability/v1/logs
    """
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

    log_provider = LoggerProvider(resource=resource)
    log_exporter = OTLPLogExporter(endpoint=logs_endpoint)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

    otel_handler = LoggingHandler(level=logging.INFO, logger_provider=log_provider)
    # Format the body as JSON so Loki can parse it
    otel_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    logging.getLogger().addHandler(otel_handler)
