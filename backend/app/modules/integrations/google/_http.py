"""Shared HTTP layer for Google API calls.

Provides:
- Connection-pooled ``httpx.AsyncClient`` (module-level singleton)
- Exponential-backoff retry for transient errors (429, 5xx)
- Structured ``GoogleAPIError`` with error classification
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ── Defaults ─────────────────────────────────────────────────

_DEFAULT_TIMEOUT = 20.0
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0  # seconds
_BACKOFF_FACTOR = 2.0
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503})


# ── Error types ──────────────────────────────────────────────


class GoogleAPIError(Exception):
    """Structured error from a Google API call."""

    def __init__(
        self,
        status_code: int,
        error_type: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.retryable = retryable
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.error_type}] {super().__str__()} (HTTP {self.status_code})"


def _classify_error(resp: httpx.Response) -> GoogleAPIError:
    """Turn an HTTP error response into a classified ``GoogleAPIError``."""
    status = resp.status_code

    # Try to extract Google's error message
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message", resp.text[:200])
    except Exception:
        msg = resp.text[:200] if resp.text else f"HTTP {status}"

    if status == 401:
        return GoogleAPIError(status, "auth_expired", msg)
    if status == 403:
        # Google uses 403 for both permission denied AND rate limits
        if "rate" in msg.lower() or "quota" in msg.lower():
            return GoogleAPIError(status, "rate_limited", msg, retryable=True)
        return GoogleAPIError(status, "permission_denied", msg)
    if status == 404:
        return GoogleAPIError(status, "not_found", msg)
    if status == 429:
        return GoogleAPIError(status, "rate_limited", msg, retryable=True)
    if status >= 500:
        return GoogleAPIError(status, "server_error", msg, retryable=True)
    return GoogleAPIError(status, "api_error", msg)


# ── Connection-pooled client ─────────────────────────────────

_shared_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a module-level ``httpx.AsyncClient`` for connection reuse."""
    global _shared_client  # noqa: PLW0603
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            limits=httpx.Limits(
                max_connections=40,
                max_keepalive_connections=20,
                keepalive_expiry=120,
            ),
            follow_redirects=False,
        )
    return _shared_client


# ── Core request with retry ──────────────────────────────────


async def google_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    max_retries: int = _MAX_RETRIES,
    timeout: float | None = None,
) -> httpx.Response:
    """Make an HTTP request to a Google API with retry on transient errors.

    Raises ``GoogleAPIError`` for non-retryable failures.
    """
    client = _get_client()
    backoff = _INITIAL_BACKOFF

    last_error: GoogleAPIError | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "google_api_timeout",
                url=url,
                attempt=attempt + 1,
                error=str(exc),
            )
            if attempt == max_retries:
                raise GoogleAPIError(
                    0, "timeout", f"Request timed out after {max_retries + 1} attempts"
                ) from exc
            await asyncio.sleep(backoff)
            backoff *= _BACKOFF_FACTOR
            continue
        except httpx.HTTPError as exc:
            raise GoogleAPIError(0, "network_error", str(exc)) from exc

        if resp.is_success:
            return resp

        # Non-success — classify
        err = _classify_error(resp)

        if err.retryable and attempt < max_retries:
            # Respect Retry-After if present (rate limit)
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else backoff
            logger.warning(
                "google_api_retrying",
                url=url,
                status=resp.status_code,
                error_type=err.error_type,
                attempt=attempt + 1,
                wait_seconds=wait,
            )
            await asyncio.sleep(wait)
            backoff *= _BACKOFF_FACTOR
            last_error = err
            continue

        raise err

    # Exhausted retries
    raise last_error or GoogleAPIError(0, "unknown", "Retry budget exhausted")
