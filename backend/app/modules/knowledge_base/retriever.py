"""Knowledge Base module — RAG retrieval for live calls.

Provides ``KnowledgeRetriever`` which:
1. Embeds the user's query via Azure OpenAI
2. Runs pgvector cosine similarity search across the agent's attached KBs
3. Returns top-k chunks above the similarity threshold
4. Formats chunks as context for injection into the LLM system prompt

Target: <50ms total retrieval latency (embedding + vector search).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.modules.knowledge_base.service import generate_embeddings_batch

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    """A chunk retrieved from vector search."""

    chunk_text: str
    similarity: float
    document_name: str
    document_id: uuid.UUID
    kb_id: uuid.UUID


class KnowledgeRetriever:
    """Vector search retriever for RAG — used during live Pipecat calls.

    Each call to ``retrieve()`` opens its own short-lived DB session so the
    retriever works correctly even when called from a long-running background
    pipeline task (after the originating FastAPI request session has closed).

    Usage in pipeline:
        retriever = KnowledgeRetriever(agent_id)
        chunks = await retriever.retrieve("What are your office hours?")
        context = retriever.format_context(chunks)
        # Inject `context` into the LLM system prompt
    """

    def __init__(
        self,
        agent_id: uuid.UUID,
        chunk_count: int = 3,
        similarity_threshold: float = 0.25,
    ) -> None:
        self.agent_id = agent_id
        self.chunk_count = chunk_count
        self.similarity_threshold = similarity_threshold

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        """Embed the query and run vector similarity search.

        Returns top-k chunks from all KBs attached to this agent,
        filtered by cosine similarity threshold.
        """
        import time as _time
        from app.core.metrics import KB_SEARCH_LATENCY_SECONDS
        _t0 = _time.monotonic()

        if not query.strip():
            return []

        # 1. Embed the query (pure API call — no DB needed)
        embeddings = await generate_embeddings_batch([query])
        query_embedding = embeddings[0]

        # 2. Vector search — open a fresh session per retrieve() call so this
        #    works from background pipeline tasks after the request session closes.
        async with async_session_factory() as db:
            # Fast check: skip if agent has no KBs attached
            has_kb = await db.execute(
                text(
                    "SELECT 1 FROM agent_knowledge_bases WHERE agent_id = :agent_id LIMIT 1"
                ).bindparams(agent_id=self.agent_id)
            )
            if has_kb.first() is None:
                return []

            result = await db.execute(
                text(
                    """
                    SELECT
                        e.chunk_text,
                        1 - (e.embedding <=> CAST(:query_embedding AS vector)) AS similarity,
                        d.name AS document_name,
                        e.document_id,
                        e.kb_id
                    FROM kb_embeddings e
                    JOIN kb_documents d ON e.document_id = d.id
                    JOIN agent_knowledge_bases akb ON e.kb_id = akb.kb_id
                    WHERE akb.agent_id = :agent_id
                      AND 1 - (e.embedding <=> CAST(:query_embedding AS vector)) >= :threshold
                    ORDER BY e.embedding <=> CAST(:query_embedding AS vector) ASC
                    LIMIT :limit
                    """
                ).bindparams(
                    agent_id=self.agent_id,
                    query_embedding=str(query_embedding),
                    threshold=self.similarity_threshold,
                    limit=self.chunk_count,
                )
            )
            rows = result.fetchall()
        chunks = [
            RetrievedChunk(
                chunk_text=row.chunk_text,
                similarity=float(row.similarity),
                document_name=row.document_name,
                document_id=row.document_id,
                kb_id=row.kb_id,
            )
            for row in rows
        ]

        KB_SEARCH_LATENCY_SECONDS.observe(_time.monotonic() - _t0)
        logger.info(
            "rag_retrieve",
            agent_id=str(self.agent_id),
            query_length=len(query),
            results=len(chunks),
            top_similarity=chunks[0].similarity if chunks else 0.0,
        )

        return chunks

    @staticmethod
    def format_context(chunks: list[RetrievedChunk]) -> str:
        """Format retrieved chunks into a context block for LLM injection.

        Returns an empty string if no chunks are provided.
        """
        if not chunks:
            return ""

        lines = ["[Knowledge Base Context]"]
        for i, chunk in enumerate(chunks, 1):
            lines.append(f"[Source {i}: {chunk.document_name}]")
            lines.append(chunk.chunk_text)
            lines.append("")

        return "\n".join(lines)

    async def retrieve_and_format(self, query: str) -> str:
        """Convenience: retrieve + format in one call."""
        chunks = await self.retrieve(query)
        return self.format_context(chunks)


async def search_kb(
    db: AsyncSession,
    kb_id: uuid.UUID,
    query: str,
    limit: int = 5,
    threshold: float = 0.5,
) -> list[RetrievedChunk]:
    """Search a specific KB (for the API search endpoint)."""
    embeddings = await generate_embeddings_batch([query])
    query_embedding = embeddings[0]

    result = await db.execute(
        text(
            """
            SELECT
                e.chunk_text,
                1 - (e.embedding <=> CAST(:query_embedding AS vector)) AS similarity,
                d.name AS document_name,
                e.document_id,
                e.kb_id
            FROM kb_embeddings e
            JOIN kb_documents d ON e.document_id = d.id
            WHERE e.kb_id = :kb_id
              AND 1 - (e.embedding <=> CAST(:query_embedding AS vector)) >= :threshold
            ORDER BY e.embedding <=> CAST(:query_embedding AS vector) ASC
            LIMIT :limit
            """
        ).bindparams(
            kb_id=kb_id,
            query_embedding=str(query_embedding),
            threshold=threshold,
            limit=limit,
        )
    )

    rows = result.fetchall()
    return [
        RetrievedChunk(
            chunk_text=row.chunk_text,
            similarity=float(row.similarity),
            document_name=row.document_name,
            document_id=row.document_id,
            kb_id=kb_id,
        )
        for row in rows
    ]
