"""Campaign rate limiter — Redis-based concurrency and rate control.

Provides two mechanisms:
1. Counting semaphore for max_concurrent calls
2. Token bucket for calls_per_minute rate limiting
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class CampaignRateLimiter:
    """Redis-based rate limiter for campaign call pacing.

    Uses:
    - campaign:{id}:semaphore   — counting semaphore for max_concurrent
    - campaign:{id}:rate        — token bucket for calls_per_minute
    - campaign:{id}:status      — campaign status cache
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    def _sem_key(self, campaign_id: str) -> str:
        return f"campaign:{campaign_id}:semaphore"

    def _rate_key(self, campaign_id: str) -> str:
        return f"campaign:{campaign_id}:rate"

    def _status_key(self, campaign_id: str) -> str:
        return f"campaign:{campaign_id}:status"

    async def acquire_call_slot(
        self,
        campaign_id: str,
        max_concurrent: int,
        calls_per_minute: int,
        timeout: float = 60.0,
    ) -> bool:
        """Block until a concurrent slot opens AND rate limit allows.

        Returns True if slot acquired, False if timeout or campaign stopped.
        """
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            # Check if campaign is still running
            status = await self._redis.get(self._status_key(campaign_id))
            if status and status.decode() in ("paused", "cancelled"):
                return False

            # Try to acquire concurrent slot
            sem_key = self._sem_key(campaign_id)
            current = await self._redis.get(sem_key)
            current_count = int(current) if current else 0

            if current_count >= max_concurrent:
                # No slots available, wait and retry
                await self._sleep(0.5)
                continue

            # Try to acquire rate limit token
            if not await self._try_acquire_token(campaign_id, calls_per_minute):
                # Rate limited, wait and retry
                await self._sleep(0.1)
                continue

            # Increment semaphore
            await self._redis.incr(sem_key)
            await self._redis.expire(sem_key, 3600)  # 1hr TTL
            return True

        return False

    async def release_call_slot(self, campaign_id: str) -> None:
        """Release one concurrent slot."""
        sem_key = self._sem_key(campaign_id)
        current = await self._redis.get(sem_key)
        if current and int(current) > 0:
            await self._redis.decr(sem_key)

    async def _try_acquire_token(self, campaign_id: str, calls_per_minute: int) -> bool:
        """Token bucket implementation for rate limiting.

        Returns True if a token was acquired, False otherwise.
        """
        rate_key = self._rate_key(campaign_id)
        now = time.time()

        # Lua script for atomic token bucket check and update
        lua_script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local now = tonumber(ARGV[2])
        local window = 60.0

        local data = redis.call('GET', key)
        local tokens = rate
        local last_update = now

        if data then
            local parts = {}
            for part in string.gmatch(data, "[^:]+") do
                table.insert(parts, part)
            end
            tokens = tonumber(parts[1])
            last_update = tonumber(parts[2])
        end

        -- Refill tokens based on elapsed time
        local elapsed = now - last_update
        local refill = (elapsed / window) * rate
        tokens = math.min(rate, tokens + refill)

        if tokens >= 1 then
            tokens = tokens - 1
            redis.call('SET', key, tokens .. ':' .. now, 'EX', 120)
            return 1
        else
            redis.call('SET', key, tokens .. ':' .. now, 'EX', 120)
            return 0
        end
        """
        result = await self._redis.eval(lua_script, 1, rate_key, calls_per_minute, now)
        return bool(result)

    async def check_calling_window(
        self,
        calling_window: dict[str, Any] | None,
    ) -> bool:
        """Return True if current time is within the calling window."""
        if not calling_window:
            return True

        tz_name = calling_window.get("timezone", "UTC")
        start_time = calling_window.get("start", "00:00")
        end_time = calling_window.get("end", "23:59")
        allowed_days = calling_window.get("days", [0, 1, 2, 3, 4, 5, 6])

        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(tz_name)
        except Exception:
            tz = timezone.utc

        now = datetime.now(tz)
        current_day = now.weekday()
        current_time = now.strftime("%H:%M")

        if current_day not in allowed_days:
            return False

        return start_time <= current_time <= end_time

    async def set_campaign_status(self, campaign_id: str, status: str) -> None:
        """Cache campaign status in Redis for fast checks."""
        await self._redis.set(
            self._status_key(campaign_id),
            status,
            ex=3600,  # 1hr TTL
        )

    async def get_campaign_status(self, campaign_id: str) -> str | None:
        """Get cached campaign status."""
        result = await self._redis.get(self._status_key(campaign_id))
        return result.decode() if result else None

    async def clear_campaign_keys(self, campaign_id: str) -> None:
        """Clean up all Redis keys for a campaign."""
        await self._redis.delete(
            self._sem_key(campaign_id),
            self._rate_key(campaign_id),
            self._status_key(campaign_id),
        )

    async def get_active_calls_count(self, campaign_id: str) -> int:
        """Get current number of active concurrent calls."""
        sem_key = self._sem_key(campaign_id)
        current = await self._redis.get(sem_key)
        return int(current) if current else 0

    async def _sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio

        await asyncio.sleep(seconds)


class GlobalRateLimiter:
    """Platform-wide guard — enforces a global maximum of concurrent calls.

    Uses an atomic Redis Lua script so that the incr/check is race-free
    across all workers and pods.

    Key: ``SphereVoice:global:active_calls`` (integer counter with 1-hour TTL).
    """

    GLOBAL_KEY = "SphereVoice:global:active_calls"
    _TTL = 3600  # 1hr safety TTL

    # Lua: atomically increment only if current count < ceiling.
    # Returns 1 if slot acquired, 0 if at capacity.
    _ACQUIRE_LUA = """
    local key = KEYS[1]
    local max_calls = tonumber(ARGV[1])
    local current = tonumber(redis.call('GET', key) or '0')
    if current < max_calls then
        redis.call('INCR', key)
        redis.call('EXPIRE', key, ARGV[2])
        return 1
    end
    return 0
    """

    # Lua: atomically decrement but never go below 0.
    _RELEASE_LUA = """
    local key = KEYS[1]
    local current = tonumber(redis.call('GET', key) or '0')
    if current > 0 then
        redis.call('DECR', key)
    end
    return current - 1
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def acquire_global_slot(self, max_calls: int | None = None) -> bool:
        """Try to acquire one global slot.

        Args:
            max_calls: Ceiling for concurrent calls.  Falls back to
                ``settings.GLOBAL_MAX_CONCURRENT_CALLS`` when *None*.

        Returns:
            ``True`` if a slot was acquired, ``False`` if at capacity.
        """
        if max_calls is None:
            max_calls = settings.GLOBAL_MAX_CONCURRENT_CALLS
        result = await self._redis.eval(self._ACQUIRE_LUA, 1, self.GLOBAL_KEY, max_calls, self._TTL)
        return bool(result)

    async def release_global_slot(self) -> None:
        """Release one global slot (safe if counter is already 0)."""
        await self._redis.eval(self._RELEASE_LUA, 1, self.GLOBAL_KEY)

    async def get_global_active_count(self) -> int:
        """Return current number of globally active calls."""
        val = await self._redis.get(self.GLOBAL_KEY)
        return int(val) if val else 0
