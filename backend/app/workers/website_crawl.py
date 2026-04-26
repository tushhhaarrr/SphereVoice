"""Website crawl + KB seeding task.

Uses the Firecrawl API to crawl a tenant's website (up to 25 pages),
converts each page to Markdown, stores it as a KBDocument, then
queues the existing generate_embeddings task for vector processing.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import uuid
from urllib.parse import urlparse

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


# ── SSRF guard ──────────────────────────────────────────────────


_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _assert_url_is_safe(url: str) -> None:
    """Raise ValueError if the URL resolves to a private/loopback address."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsafe URL scheme: {parsed.scheme!r}. Only http/https are allowed.")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("URL has no hostname.")

    # Reject bare hostnames like 'localhost'
    if hostname.lower() in ("localhost", "metadata.google.internal"):
        raise ValueError(f"Hostname {hostname!r} is not allowed.")

    # Resolve and check all returned addresses
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname {hostname!r}: {exc}") from exc

    for _, _, _, _, sockaddr in addr_infos:
        raw_ip = sockaddr[0]
        try:
            addr = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        for net in _PRIVATE_NETS:
            if addr in net:
                raise ValueError(
                    f"URL resolves to a private/loopback address ({raw_ip}), which is not allowed."
                )


# ── Async implementation ────────────────────────────────────────


def _run_async(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from sync Celery task context."""
    from app.core.database import async_engine

    loop = asyncio.new_event_loop()
    try:
        try:
            loop.run_until_complete(async_engine.dispose())
        except RuntimeError:
            pass
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _set_kb_status(session_factory, kb_id: uuid.UUID, status: str) -> None:
    """Update the KB status column in a short-lived session."""
    from sqlalchemy import text as sqlt

    async with session_factory() as db:
        await db.execute(
            sqlt("UPDATE knowledge_bases SET status = :s WHERE id = :kb_id"),
            {"s": status, "kb_id": str(kb_id)},
        )
        await db.commit()


async def _do_crawl_and_seed(
    kb_id: uuid.UUID,
    website_url: str,
    tenant_id: uuid.UUID,
) -> dict[str, object]:
    """Crawl the website, create text documents, queue embeddings.

    Creates a per-invocation NullPool engine so no asyncpg connections are
    shared across Celery tasks that each run their own event loop.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings
    from app.modules.agents.models import Agent, AgentKnowledgeBase, AgentVersion  # noqa: F401 — registers mapper
    from app.modules.knowledge_base.service import KnowledgeBaseService
    from app.workers.embeddings import generate_embeddings

    settings = get_settings()

    if not settings.FIRECRAWL_API_KEY:
        raise RuntimeError(
            "FIRECRAWL_API_KEY is not configured. Cannot crawl website."
        )

    # SSRF guard — run synchronously before any network call
    _assert_url_is_safe(website_url)

    from firecrawl import V1FirecrawlApp, V1ScrapeOptions  # type: ignore[import-untyped]

    firecrawl = V1FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Mark KB as processing so the UI can show a spinner
    await _set_kb_status(session_factory, kb_id, "processing")

    logger.info("website_crawl_start", kb_id=str(kb_id), url=website_url)

    try:
        crawl_result = firecrawl.crawl_url(
            website_url,
            limit=25,
            scrape_options=V1ScrapeOptions(formats=["markdown"]),
            poll_interval=5,
        )
    except Exception:
        await _set_kb_status(session_factory, kb_id, "failed")
        await engine.dispose()
        raise

    # firecrawl-py returns either a CrawlStatusResponse or a dict depending on version
    raw_pages: list[object] = []
    if hasattr(crawl_result, "data"):
        raw_pages = crawl_result.data or []
    elif isinstance(crawl_result, dict):
        raw_pages = crawl_result.get("data", [])

    pages_indexed = 0
    crawl_succeeded = False
    try:
        async with session_factory() as db:
            for page in raw_pages:
                # Support both object-style and dict-style page results
                if hasattr(page, "markdown"):
                    content = page.markdown or ""
                    metadata = getattr(page, "metadata", {}) or {}
                elif isinstance(page, dict):
                    content = page.get("markdown") or ""
                    metadata = page.get("metadata", {}) or {}
                else:
                    continue

                if not content.strip():
                    continue

                # Extract title
                title: str = (
                    (metadata.get("title") if isinstance(metadata, dict) else getattr(metadata, "title", None))
                    or ""
                )
                # Extract the page URL to disambiguate pages with the same title
                page_url: str = (
                    (metadata.get("url") or metadata.get("sourceURL") if isinstance(metadata, dict)
                     else getattr(metadata, "url", None) or getattr(metadata, "sourceURL", None))
                    or website_url
                )
                path = urlparse(page_url).path.rstrip("/") or "/"
                if title and path and path != "/":
                    display_name = f"{title} ({path})"
                else:
                    display_name = title or page_url
                # Trim to a reasonable document name length
                if len(display_name) > 255:
                    display_name = display_name[:252] + "..."

                doc = await KnowledgeBaseService.add_text_document(
                    db, kb_id, name=display_name, content=content
                )
                await db.commit()

                # Queue embedding generation for this document
                generate_embeddings.delay(str(doc.id))
                pages_indexed += 1

        crawl_succeeded = True
    except Exception:
        await _set_kb_status(session_factory, kb_id, "failed")
        raise
    finally:
        if crawl_succeeded:
            await _set_kb_status(session_factory, kb_id, "ready")
        await engine.dispose()

    logger.info(
        "website_crawl_complete",
        kb_id=str(kb_id),
        url=website_url,
        pages_indexed=pages_indexed,
    )
    return {
        "status": "completed",
        "kb_id": str(kb_id),
        "website_url": website_url,
        "pages_indexed": pages_indexed,
    }


# ── Celery task ─────────────────────────────────────────────────


@celery_app.task(
    name="app.workers.website_crawl.crawl_website_and_seed_kb",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def crawl_website_and_seed_kb(
    self: object,
    kb_id: str,
    website_url: str,
    tenant_id: str,
) -> dict[str, object]:
    """Crawl a tenant's website and populate a KB with the crawled pages.

    Args:
        kb_id: UUID string of the target KnowledgeBase record.
        website_url: The root URL to crawl (must be http/https, no private IPs).
        tenant_id: UUID string of the owning tenant (for logging).
    """
    logger.info(
        "website_crawl_task_start",
        kb_id=kb_id,
        url=website_url,
        tenant_id=tenant_id,
        task_id=getattr(getattr(self, "request", None), "id", None),
    )
    return _run_async(
        _do_crawl_and_seed(
            kb_id=uuid.UUID(kb_id),
            website_url=website_url,
            tenant_id=uuid.UUID(tenant_id),
        )
    )
