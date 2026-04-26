"""Campaign queue abstraction — Redis or Azure Service Bus backend.

Provides a unified interface for enqueuing and consuming campaign
call tasks.  The backend is selected by CELERY_BROKER_BACKEND:
  - "redis"      → uses Celery's standard Redis broker (local dev)
  - "servicebus" → direct Azure Service Bus SDK for richer features
                    (scheduled delivery, sessions, dead-letter)

For non-campaign tasks the Celery broker swap (celery_app.py) is
sufficient.  This module exists because campaigns need ASB-specific
features that Celery/Kombu don't expose: scheduled enqueue time,
per-campaign session IDs, and peek at dead-letter queues.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class CampaignQueue(ABC):
    """Abstract interface for campaign call scheduling."""

    @abstractmethod
    async def enqueue(
        self,
        campaign_id: str,
        contact_payload: dict[str, Any],
        *,
        scheduled_at: datetime | None = None,
    ) -> str:
        """Enqueue a single contact for dialling.

        Returns a message ID.
        If *scheduled_at* is set, the message becomes visible only at
        that time (ASB scheduled enqueue; Redis falls back to Celery ETA).
        """

    @abstractmethod
    async def dead_letter_count(self, campaign_id: str) -> int:
        """Return the number of messages stuck in the dead-letter sub-queue."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying connections."""


# ── Redis-backed implementation (local dev / simple deploys) ─────


class RedisCampaignQueue(CampaignQueue):
    """Delegates to Celery's Redis broker with ETA for scheduling."""

    async def enqueue(
        self,
        campaign_id: str,
        contact_payload: dict[str, Any],
        *,
        scheduled_at: datetime | None = None,
    ) -> str:
        from app.workers.celery_app import celery_app

        kwargs = {
            "campaign_id": campaign_id,
            "contact": contact_payload,
        }
        result = celery_app.send_task(
            "app.workers.campaign_call.execute_campaign_call",
            kwargs=kwargs,
            eta=scheduled_at,
        )
        return result.id

    async def dead_letter_count(self, campaign_id: str) -> int:
        # Redis broker has no native DLQ — return 0
        return 0

    async def close(self) -> None:
        pass  # Celery manages its own connections


# ── Azure Service Bus implementation (cloud deployments) ─────


class ServiceBusCampaignQueue(CampaignQueue):
    """Uses azure-servicebus SDK for richer delivery guarantees."""

    def __init__(self) -> None:
        from azure.servicebus.aio import ServiceBusClient

        conn_str = settings.AZURE_SERVICE_BUS_CONNECTION_STRING
        if not conn_str:
            raise RuntimeError(
                "ServiceBusCampaignQueue requires "
                "AZURE_SERVICE_BUS_CONNECTION_STRING"
            )
        self._client = ServiceBusClient.from_connection_string(conn_str)
        prefix = settings.AZURE_SERVICE_BUS_QUEUE_PREFIX
        self._queue_name = f"{prefix}-campaign-calls"

    async def enqueue(
        self,
        campaign_id: str,
        contact_payload: dict[str, Any],
        *,
        scheduled_at: datetime | None = None,
    ) -> str:
        from azure.servicebus import ServiceBusMessage

        sender = self._client.get_queue_sender(self._queue_name)
        async with sender:
            body = json.dumps({
                "campaign_id": campaign_id,
                "contact": contact_payload,
            })
            msg = ServiceBusMessage(
                body=body,
                session_id=campaign_id,  # per-campaign FIFO ordering
                subject="campaign_call",
            )
            if scheduled_at is not None:
                msg.scheduled_enqueue_time_utc = scheduled_at
            await sender.send_messages(msg)
            return msg.message_id or ""

    async def dead_letter_count(self, campaign_id: str) -> int:
        from azure.servicebus.management.aio import ServiceBusAdministrationClient

        conn_str = settings.AZURE_SERVICE_BUS_CONNECTION_STRING
        admin = ServiceBusAdministrationClient.from_connection_string(conn_str)
        async with admin:
            props = await admin.get_queue_runtime_properties(self._queue_name)
            return props.dead_letter_message_count

    async def close(self) -> None:
        await self._client.close()


# ── Factory ──────────────────────────────────────────────────


def get_campaign_queue() -> CampaignQueue:
    """Return the appropriate CampaignQueue based on config."""
    if settings.CELERY_BROKER_BACKEND == "servicebus":
        return ServiceBusCampaignQueue()
    return RedisCampaignQueue()
