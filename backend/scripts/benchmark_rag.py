#!/usr/bin/env python3
"""RAG Vector Search Benchmark — proves <50ms P50 latency at 100K+ chunks.

Usage:
    python scripts/benchmark_rag.py                          # default 100K chunks, 100 queries
    python scripts/benchmark_rag.py --chunks 200000 --queries 200
    python scripts/benchmark_rag.py --skip-insert --queries 500   # reuse existing data

What it does:
    1. Creates a temporary tenant, KB, and document
    2. Inserts N synthetic 1536-dim embeddings via raw asyncpg COPY
    3. Runs M vector similarity queries using the HNSW index
    4. Reports P50 / P95 / P99 / max latency
    5. Cleans up all synthetic data (unless --keep)

Requires: DATABASE_URL in .env, running PostgreSQL with pgvector + HNSW index.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
import uuid
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from app.core.config import get_settings

EMBEDDING_DIM = 1536
BATCH_SIZE = 5000


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RAG vector search latency benchmark")
    p.add_argument("--chunks", type=int, default=100_000)
    p.add_argument("--queries", type=int, default=100)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--threshold", type=float, default=0.3)
    p.add_argument("--skip-insert", action="store_true")
    p.add_argument("--keep", action="store_true")
    return p.parse_args()


def dsn_from_async_url(url: str) -> str:
    """Convert asyncpg:// URL to plain postgresql:// for asyncpg.connect."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def setup(conn: asyncpg.Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    await conn.execute(
        "INSERT INTO tenants (id, name, slug, status) VALUES ($1, $2, $3, 'active') "
        "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name",
        tenant_id, "Benchmark Tenant", f"bench-{tenant_id.hex[:8]}",
    )
    await conn.execute(
        "INSERT INTO knowledge_bases (id, tenant_id, name, description, sharing_scope) "
        "VALUES ($1, $2, 'Benchmark KB', 'Synthetic RAG benchmark', 'tenant')",
        kb_id, tenant_id,
    )
    await conn.execute(
        "INSERT INTO kb_documents (id, kb_id, name, type, chunk_count) "
        "VALUES ($1, $2, 'benchmark.txt', 'text/plain', 0)",
        doc_id, kb_id,
    )
    return tenant_id, kb_id, doc_id


async def insert_embeddings(
    conn: asyncpg.Connection,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    total: int,
) -> None:
    """Bulk-insert synthetic embeddings using asyncpg executemany."""
    print(f"  Inserting {total:,} embeddings ({BATCH_SIZE}/batch)...")
    rng = np.random.default_rng(42)
    inserted = 0

    stmt = await conn.prepare(
        "INSERT INTO kb_embeddings (id, kb_id, document_id, chunk_text, embedding, chunk_index) "
        "VALUES ($1, $2, $3, $4, $5::vector, $6)"
    )

    while inserted < total:
        batch = min(BATCH_SIZE, total - inserted)
        vecs = rng.standard_normal((batch, EMBEDDING_DIM)).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vecs = vecs / norms

        rows = [
            (
                uuid.uuid4(),
                kb_id,
                doc_id,
                f"Benchmark chunk {inserted + i}. Synthetic text for latency testing.",
                "[" + ",".join(f"{v:.6f}" for v in vecs[i]) + "]",
                inserted + i,
            )
            for i in range(batch)
        ]

        await stmt.executemany(rows)
        inserted += batch
        pct = inserted * 100 // total
        print(f"    {inserted:>8,} / {total:,}  ({pct}%)")

    await conn.execute(
        "UPDATE kb_documents SET chunk_count = $1 WHERE id = $2", total, doc_id
    )


async def run_queries(
    conn: asyncpg.Connection,
    kb_id: uuid.UUID,
    num_queries: int,
    top_k: int,
    threshold: float,
) -> list[float]:
    """Run vector similarity queries, return latencies in ms."""
    rng = np.random.default_rng(123)
    latencies: list[float] = []

    search_sql = (
        "SELECT e.chunk_text, "
        "       1 - (e.embedding <=> $1::vector) AS similarity "
        "FROM kb_embeddings e "
        "WHERE e.kb_id = $2 "
        "  AND 1 - (e.embedding <=> $1::vector) >= $3 "
        "ORDER BY e.embedding <=> $1::vector ASC "
        "LIMIT $4"
    )

    stmt = await conn.prepare(search_sql)

    def make_vec() -> str:
        qv = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
        qv = qv / np.linalg.norm(qv)
        return "[" + ",".join(f"{v:.6f}" for v in qv) + "]"

    # Warm up
    for _ in range(5):
        await stmt.fetch(make_vec(), kb_id, threshold, top_k)

    print(f"  Running {num_queries} queries (top-{top_k}, threshold={threshold})...")

    for i in range(num_queries):
        vec_str = make_vec()
        start = time.perf_counter()
        rows = await stmt.fetch(vec_str, kb_id, threshold, top_k)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        if (i + 1) % 25 == 0:
            print(f"    Query {i + 1}/{num_queries}  last={elapsed_ms:.1f}ms  rows={len(rows)}")

    return latencies


async def cleanup(conn: asyncpg.Connection, tenant_id: uuid.UUID, kb_id: uuid.UUID) -> None:
    print("  Cleaning up...")
    await conn.execute("DELETE FROM kb_embeddings WHERE kb_id = $1", kb_id)
    await conn.execute("DELETE FROM kb_documents WHERE kb_id = $1", kb_id)
    await conn.execute("DELETE FROM knowledge_bases WHERE id = $1", kb_id)
    await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)


def print_report(latencies: list[float], num_chunks: int) -> bool:
    s = sorted(latencies)
    n = len(s)
    p50 = s[int(n * 0.50)]
    p95 = s[int(n * 0.95)]
    p99 = s[min(int(n * 0.99), n - 1)]
    p_max = s[-1]
    mean = statistics.mean(s)
    stddev = statistics.stdev(s) if n > 1 else 0.0
    ok = p50 < 50.0

    print("\n" + "=" * 60)
    print("  RAG Vector Search Benchmark Results")
    print(f"  Chunks: {num_chunks:,}  |  Queries: {n}")
    print("=" * 60)
    print(f"  Mean:   {mean:8.2f} ms")
    print(f"  StdDev: {stddev:8.2f} ms")
    print(f"  P50:    {p50:8.2f} ms  {'PASS' if p50 < 50 else 'FAIL'}  (SLA: <50ms)")
    print(f"  P95:    {p95:8.2f} ms")
    print(f"  P99:    {p99:8.2f} ms")
    print(f"  Max:    {p_max:8.2f} ms")
    print("=" * 60)
    print(f"  RESULT: {'PASS' if ok else 'FAIL'} — P50 {'under' if ok else 'exceeds'} 50ms SLA")
    print("=" * 60 + "\n")
    return ok


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    dsn = dsn_from_async_url(settings.DATABASE_URL)

    conn = await asyncpg.connect(dsn)
    tenant_id = kb_id = doc_id = None
    sla_pass = False

    try:
        print("\n[1/4] Setting up synthetic data...")
        tenant_id, kb_id, doc_id = await setup(conn)
        print(f"  Tenant: {tenant_id}\n  KB:     {kb_id}")

        if not args.skip_insert:
            print(f"\n[2/4] Inserting {args.chunks:,} embeddings...")
            await insert_embeddings(conn, kb_id, doc_id, args.chunks)
            print("  Done.")
        else:
            print("\n[2/4] Skipping insert (--skip-insert)")

        print("\n[3/4] Running benchmark queries...")
        latencies = await run_queries(conn, kb_id, args.queries, args.top_k, args.threshold)

        print("\n[4/4] Results:")
        sla_pass = print_report(latencies, args.chunks)

    finally:
        if not args.keep and tenant_id and kb_id:
            await cleanup(conn, tenant_id, kb_id)
        elif args.keep and kb_id:
            print(f"  Keeping data — KB ID: {kb_id}")
        await conn.close()

    if not sla_pass:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
