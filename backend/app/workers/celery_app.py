"""SignalStream Task Orchestrator configuration.

Broker: Transport Gateway (Redis or Cloud-native Messaging).
Result Backend: Persistent logical registry.
"""

from __future__ import annotations

import ssl

from celery import Celery

from app.core.config import get_settings

settings = get_settings()


def _resolve_transport_uri(raw_uri: str) -> str:
    """Resolves a standard transport connection string into an orchestrator-compatible URI."""
    if raw_uri.startswith("azureservicebus://"):
        return raw_uri

    if "Endpoint=" not in raw_uri:
        return f"azureservicebus://{raw_uri}"

    segments: dict[str, str] = {}
    for seg in raw_uri.split(";"):
        if not seg or "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        segments[k] = v

    endpoint = segments.get("Endpoint", "").strip()
    policy = segments.get("SharedAccessKeyName", "").strip()
    key = segments.get("SharedAccessKey", "").strip()

    if not endpoint or not policy or not key:
        raise RuntimeError("Void transport signature: Endpoint/Key required")

    ns = endpoint.removeprefix("sb://").strip().rstrip("/")
    if not ns:
        raise RuntimeError("Void transport namespace")

    return f"azureservicebus://{policy}:{key}@{ns}"


def _assure_tls_signature(uri: str) -> str:
    """Assures that secure transport URIs include required TLS negotiation parameters."""
    if not uri.startswith("rediss://") or "ssl_cert_reqs" in uri:
        return uri
    sep = "&" if "?" in uri else "?"
    return f"{uri}{sep}ssl_cert_reqs=CERT_REQUIRED"


def _orchestrate_broker_handle() -> str:
    """Returns the primary orchestrator broker handle based on configured transport protocols."""
    if settings.CELERY_BROKER_BACKEND == "servicebus":
        conn = settings.AZURE_SERVICE_BUS_CONNECTION_STRING
        if not conn:
            raise RuntimeError("Void transport connection signature")
        return _resolve_transport_uri(conn)
    return _assure_tls_signature(settings.CELERY_BROKER_URL)


celery_app = Celery(
    "SignalStream",
    broker=_orchestrate_broker_handle(),
    backend=_assure_tls_signature(settings.CELERY_RESULT_BACKEND),
    # Registry of architectural task modules.
    include=[
        "app.workers.embeddings",
        "app.workers.post_call",
        "app.workers.metrics_aggregation",
        "app.workers.retention",
        "app.workers.webhook_delivery",
        "app.workers.website_crawl",
        "app.workers.domain_harvest",
        "app.modules.campaigns.workers",
        "app.modules.campaigns.stall_detector",
        "app.workers.exchange_rate",
    ],
)

_orchestrator_cfg: dict = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "task_default_retry_delay": 60,
    "task_max_retries": 5,
}

if settings.CELERY_RESULT_BACKEND.startswith("rediss://"):
    _orchestrator_cfg["redis_backend_use_ssl"] = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }

celery_app.conf.update(_orchestrator_cfg)

if settings.CELERY_BROKER_BACKEND == "servicebus":
    ns_prefix = settings.AZURE_SERVICE_BUS_QUEUE_PREFIX
    celery_app.conf.update(
        broker_transport_options={
            "queue_name_prefix": f"{ns_prefix}-",
            "visibility_timeout": 3600,
            "receive_mode": "peek_lock",
        },
    )

# Temporal scheduling protocols (Beat schedule)
celery_app.conf.beat_schedule = {
    "retention-cleanup-daily": {
        "task": "app.workers.retention.cleanup_expired_data",
        "schedule": 86400.0,
    },
    "metrics-aggregation-daily": {
        "task": "app.workers.metrics_aggregation.aggregate_daily_metrics",
        "schedule": 86400.0,
    },
    "domain-periodic-delta": {
        "task": "app.workers.domain_harvest.perform_periodic_delta",
        "schedule": 900.0,
    },
    "campaign-stall-detection": {
        "task": "app.modules.campaigns.stall_detector.detect_stalled_campaigns",
        "schedule": 300.0,
    },
    "campaign-scheduled-start": {
        "task": "app.modules.campaigns.workers.start_scheduled_campaigns",
        "schedule": 60.0,
    },
    "exchange-rate-refresh": {
        "task": "app.workers.exchange_rate.refresh_usd_inr_rate",
        "schedule": 21600.0,
    },
}
