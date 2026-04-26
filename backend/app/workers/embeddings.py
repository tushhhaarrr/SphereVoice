"""Document embedding tasks.

Imports from: knowledge_base module
- Chunk documents
- Generate embeddings via Azure OpenAI
- Store in pgvector
"""

from __future__ import annotations

import asyncio
import uuid

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


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


async def _process_document(document_id: uuid.UUID) -> int:
    """Process a document: extract text → chunk → embed → store vectors.

    Creates a per-invocation NullPool engine so no asyncpg connections are
    shared across Celery tasks that each run their own event loop.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings
    from app.modules.agents.models import Agent, AgentKnowledgeBase, AgentVersion  # noqa: F401 — registers mapper
    from app.modules.knowledge_base.service import KnowledgeBaseService

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as db:
            chunk_count = await KnowledgeBaseService.process_document(db, document_id)
            await db.commit()
            logger.info(
                "embedding_task_success",
                document_id=str(document_id),
                chunk_count=chunk_count,
            )
            return chunk_count
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.embeddings.generate_embeddings",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def generate_embeddings(self: object, document_id: str) -> dict[str, object]:
    """Chunk a document and generate vector embeddings.

    Called asynchronously after document upload. Retries up to 3 times
    with exponential backoff on failure.
    """
    logger.info("embedding_task_start", document_id=document_id, task_id=getattr(self, "request", None) and getattr(self, "request").id)
    doc_uuid = uuid.UUID(document_id)
    chunk_count = _run_async(_process_document(doc_uuid))
    return {"status": "completed", "document_id": document_id, "chunks": chunk_count}
