"""Spectral Manifold — Event Broadcaster.

Broadcasts real-time signal synchronisation events via Redis pub/sub.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

CHANNEL_SPECTRAL_EVENTS = "SignalStream:spectral_events"


class SpectralEventDispatcher:
    """Broadcasts signal events via the architectural Redis pub/sub substrate."""

    _redis: aioredis.Redis | None = None

    @classmethod
    async def _get_redis(cls) -> aioredis.Redis:
        if cls._redis is None:
            cls._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return cls._redis

    @classmethod
    async def publish(cls, event_class: str, data: dict[str, Any]) -> None:
        """Publish a telemetry event to the spectral events channel."""
        try:
            r = await cls._get_redis()
            message = json.dumps({"event": event_class, "data": data})
            await r.publish(CHANNEL_SPECTRAL_EVENTS, message)
        except Exception:
            logger.warning("spectral_event_broadcast_failed", event=event_class)

    @classmethod
    async def subscribe(cls) -> aioredis.client.PubSub:
        """Return a PubSub instance subscribed to the spectral events channel."""
        r = await cls._get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(CHANNEL_SPECTRAL_EVENTS)
        return pubsub

    @classmethod
    async def close(cls) -> None:
        if cls._redis:
            await cls._redis.aclose()
            cls._redis = None
