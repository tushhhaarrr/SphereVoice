"""Prometheus business metrics for SphereVoice.

Exposes counters, histograms, and gauges that capture call lifecycle,
pipeline health, and provider performance.  Scraped by Prometheus at
/metrics (mounted in main.py).

Usage in other modules::

    from app.core.metrics import CALLS_TOTAL, ACTIVE_CALLS
    CALLS_TOTAL.labels(direction="inbound", status="completed", tenant_id="...").inc()
    ACTIVE_CALLS.inc()
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.requests import Request
from starlette.responses import Response

# ── Custom registry (avoids exposing default Go-style process metrics) ──
REGISTRY = CollectorRegistry()

# ─────────────────────────────────────────────────────────────
# Call lifecycle
# ─────────────────────────────────────────────────────────────

CALLS_TOTAL = Counter(
    "SphereVoice_calls_total",
    "Total voice calls by direction and final status",
    ["direction", "status", "tenant_id"],
    registry=REGISTRY,
)

ACTIVE_CALLS = Gauge(
    "SphereVoice_active_calls",
    "Currently active voice calls",
    ["direction"],
    registry=REGISTRY,
)

CALL_DURATION_SECONDS = Histogram(
    "SphereVoice_call_duration_seconds",
    "Call duration in seconds",
    ["direction", "tenant_id"],
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600),
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# Pipeline health
# ─────────────────────────────────────────────────────────────

PIPELINE_ERRORS_TOTAL = Counter(
    "SphereVoice_pipeline_errors_total",
    "Pipeline errors by type",
    ["error_type", "tenant_id"],
    registry=REGISTRY,
)

PIPELINE_RETRIES_TOTAL = Counter(
    "SphereVoice_pipeline_retries_total",
    "Pipeline auto-retries",
    ["tenant_id"],
    registry=REGISTRY,
)

PIPELINE_CIRCUIT_BREAKS_TOTAL = Counter(
    "SphereVoice_pipeline_circuit_breaks_total",
    "Pipeline circuit breaker activations (error storm kills)",
    ["tenant_id"],
    registry=REGISTRY,
)

PIPELINE_INIT_FAILURES_TOTAL = Counter(
    "SphereVoice_pipeline_init_failures_total",
    "Pipeline initialization failures (STT/LLM/TTS unavailable)",
    ["stage", "tenant_id"],
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# Provider latency (STT / LLM / TTS)
# ─────────────────────────────────────────────────────────────

PROVIDER_LATENCY_SECONDS = Histogram(
    "SphereVoice_provider_latency_seconds",
    "Provider API latency (TTFB) in seconds",
    ["provider_category", "provider_name"],
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=REGISTRY,
)

PROVIDER_REQUEST_TOTAL = Counter(
    "SphereVoice_provider_requests_total",
    "Total requests to external providers",
    ["provider_category", "provider_name", "status"],
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# HTTP layer (supplements OTEL auto-instrumentation)
# ─────────────────────────────────────────────────────────────

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "SphereVoice_http_requests_in_progress",
    "HTTP requests currently being processed",
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "SphereVoice_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path_template", "status_code"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# WebSocket / real-time
# ─────────────────────────────────────────────────────────────

WEBSOCKET_CONNECTIONS = Gauge(
    "SphereVoice_websocket_connections",
    "Active WebSocket connections",
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# Database & infrastructure
# ─────────────────────────────────────────────────────────────

DB_QUERY_DURATION_SECONDS = Histogram(
    "SphereVoice_db_query_duration_seconds",
    "Database query duration in seconds (slow query tracking)",
    ["operation"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# CRM & Integrations
# ─────────────────────────────────────────────────────────────

CRM_SYNC_TOTAL = Counter(
    "SphereVoice_crm_sync_total",
    "CRM sync operations by module and status",
    ["module", "status"],
    registry=REGISTRY,
)

CRM_ENRICHMENT_TOTAL = Counter(
    "SphereVoice_crm_enrichment_total",
    "Caller enrichment lookups by result",
    ["status"],
    registry=REGISTRY,
)

CRM_ENRICHMENT_LATENCY_SECONDS = Histogram(
    "SphereVoice_crm_enrichment_latency_seconds",
    "CRM caller enrichment latency",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0),
    registry=REGISTRY,
)

WEBHOOK_DELIVERIES_TOTAL = Counter(
    "SphereVoice_webhook_deliveries_total",
    "Webhook delivery attempts by status",
    ["status"],
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# Worker tasks (Celery)
# ─────────────────────────────────────────────────────────────

WORKER_TASKS_TOTAL = Counter(
    "SphereVoice_worker_tasks_total",
    "Worker task completions by task name and status",
    ["task_name", "status"],
    registry=REGISTRY,
)

WORKER_TASK_DURATION_SECONDS = Histogram(
    "SphereVoice_worker_task_duration_seconds",
    "Worker task execution duration",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
    registry=REGISTRY,
)

POST_CALL_EXTRACTION_DURATION_SECONDS = Histogram(
    "SphereVoice_post_call_extraction_duration_seconds",
    "Post-call LLM extraction latency",
    ["provider"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# Knowledge Base
# ─────────────────────────────────────────────────────────────

KB_SEARCH_LATENCY_SECONDS = Histogram(
    "SphereVoice_kb_search_latency_seconds",
    "Knowledge base vector search latency",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0),
    registry=REGISTRY,
)

KB_DOCUMENTS_TOTAL = Counter(
    "SphereVoice_kb_documents_total",
    "Knowledge base document operations",
    ["operation", "status"],
    registry=REGISTRY,
)

# ─────────────────────────────────────────────────────────────
# Outbound campaigns
# ─────────────────────────────────────────────────────────────

CAMPAIGN_CALLS_TOTAL = Counter(
    "SphereVoice_campaign_calls_total",
    "Total outbound campaign calls by campaign and outcome status",
    ["campaign_id", "status"],
    registry=REGISTRY,
)

CAMPAIGN_CALLS_ACTIVE = Gauge(
    "SphereVoice_campaign_calls_active",
    "Currently active outbound campaign calls",
    ["tenant_id"],
    registry=REGISTRY,
)

CAMPAIGN_CALL_DURATION_SECONDS = Histogram(
    "SphereVoice_campaign_call_duration_seconds",
    "Outbound campaign call duration in seconds",
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600),
    registry=REGISTRY,
)

CAMPAIGN_CRM_WRITEBACK_TOTAL = Counter(
    "SphereVoice_campaign_crm_writeback_total",
    "CRM writeback attempts for campaign contacts by status",
    ["status"],
    registry=REGISTRY,
)

CAMPAIGN_QUEUE_DEPTH = Gauge(
    "SphereVoice_campaign_queue_depth",
    "Number of contacts pending in campaign queue",
    ["campaign_id"],
    registry=REGISTRY,
)


# ─────────────────────────────────────────────────────────────
# /metrics endpoint (Starlette handler for Prometheus scraping)
# ─────────────────────────────────────────────────────────────


async def metrics_endpoint(request: Request) -> Response:  # noqa: ARG001
    """Serve Prometheus metrics for scraping."""
    body = generate_latest(REGISTRY)
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)


def _init_label_combinations() -> None:
    """Pre-initialize labelled metrics so they appear in /metrics output
    immediately (before any calls or events have occurred).

    prometheus_client only exports a labelled metric once .labels() has
    been called at least once.  Without this, dashboards show "no data"
    until the first real event.
    """
    # Call lifecycle
    for direction in ("inbound", "outbound", "test"):
        for status in ("completed", "failed", "transferred"):
            CALLS_TOTAL.labels(direction=direction, status=status, tenant_id="")
        ACTIVE_CALLS.labels(direction=direction)

    # Pipeline health
    for error_type in ("stt", "llm", "tts", "pipeline", "unknown"):
        PIPELINE_ERRORS_TOTAL.labels(error_type=error_type, tenant_id="")
    PIPELINE_RETRIES_TOTAL.labels(tenant_id="")
    PIPELINE_CIRCUIT_BREAKS_TOTAL.labels(tenant_id="")
    for stage in ("stt", "llm", "tts"):
        PIPELINE_INIT_FAILURES_TOTAL.labels(stage=stage, tenant_id="")

    # Provider latency & requests
    for cat in ("stt", "llm", "tts"):
        for prov in ("deepgram", "openai", "groq", "azure", "elevenlabs", "cartesia"):
            PROVIDER_LATENCY_SECONDS.labels(provider_category=cat, provider_name=prov)
            for status in ("success", "error"):
                PROVIDER_REQUEST_TOTAL.labels(
                    provider_category=cat, provider_name=prov, status=status
                )

    # CRM & integrations
    for module in ("contacts", "deals", "leads"):
        for status in ("success", "error"):
            CRM_SYNC_TOTAL.labels(module=module, status=status)
    for status in ("cache_hit", "live", "miss", "error"):
        CRM_ENRICHMENT_TOTAL.labels(status=status)
    for status in ("success", "error"):
        WEBHOOK_DELIVERIES_TOTAL.labels(status=status)

    # Workers
    for task in ("post_call_processing", "crm_sync", "webhook_delivery"):
        for status in ("success", "error"):
            WORKER_TASKS_TOTAL.labels(task_name=task, status=status)
        WORKER_TASK_DURATION_SECONDS.labels(task_name=task)

    # Knowledge Base
    for op in ("upload", "add_text", "delete"):
        for status in ("success", "error"):
            KB_DOCUMENTS_TOTAL.labels(operation=op, status=status)

    # DB query tracking
    for op in ("select", "insert", "update", "delete"):
        DB_QUERY_DURATION_SECONDS.labels(operation=op)


_init_label_combinations()
