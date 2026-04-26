"""Backfill post-call extraction for historical calls.

Finds all completed calls that have a transcript but no extraction,
and runs the unified extraction pipeline on each — with parallelism.

Usage:
    cd backend
    python scripts/backfill_post_call_extraction.py [--dry-run] [--limit N] [--agent-id UUID] [--concurrency 5]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select, text

from app.core.database import async_session_factory
from app.modules.agents.models import Agent
from app.modules.calls.models import Call

# Ensure all models are imported so relationships resolve
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.phone_numbers import models as _phone_models  # noqa: F401
from app.modules.knowledge_base import models as _kb_models  # noqa: F401


async def _process_one_call(
    call_id: UUID,
    agent_id: UUID,
    transcript: list,
    index: int,
    total: int,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Process a single call in its own DB session. Returns True on success."""
    from app.modules.pipeline.extraction import run_post_call_extraction

    async with semaphore:
        async with async_session_factory() as db:
            await db.execute(text("SET app.current_tenant_id = ''"))

            agent = await db.get(Agent, agent_id)
            if not agent:
                print(f"  [{index}/{total}] SKIP call={call_id} — agent not found")
                return False

            try:
                extracted = await run_post_call_extraction(
                    db=db,
                    call_id=call_id,
                    agent=agent,
                    transcript=transcript,
                )
                await db.commit()

                field_count = len(extracted) if extracted else 0
                summary = (extracted.get("call_summary", "") or "")[:80]
                print(
                    f"  [{index}/{total}] OK   call={call_id}  "
                    f"fields={field_count}  summary={summary!r}"
                )
                return True
            except Exception as exc:
                print(f"  [{index}/{total}] FAIL call={call_id} — {exc}")
                return False


async def backfill(
    dry_run: bool = False,
    limit: int | None = None,
    agent_id: UUID | None = None,
    concurrency: int = 5,
) -> None:
    # Build query for calls needing extraction
    query = (
        select(Call)
        .where(
            Call.status.in_(["completed", "ended"]),
            Call.transcript.isnot(None),
            func.jsonb_array_length(Call.transcript) > 0,
            Call.extraction_completed_at.is_(None),
        )
        .order_by(Call.created_at.asc())
    )

    if agent_id:
        query = query.where(Call.agent_id == agent_id)

    if limit:
        query = query.limit(limit)

    # Fetch all call IDs + metadata in a single read session
    async with async_session_factory() as db:
        await db.execute(text("SET app.current_tenant_id = ''"))
        result = await db.execute(query)
        calls = result.scalars().all()
        # Snapshot the data we need so we can close this session
        call_data = [
            (call.id, call.agent_id, call.transcript, call.created_at)
            for call in calls
        ]

    total = len(call_data)
    print(f"Found {total} calls needing extraction (concurrency={concurrency})")

    if dry_run:
        for call_id, agent_id_val, transcript, created_at in call_data:
            print(
                f"  [DRY RUN] call={call_id}  agent={agent_id_val}  "
                f"transcript_entries={len(transcript)}  "
                f"created={created_at}"
            )
        return

    t0 = time.monotonic()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _process_one_call(
            call_id=call_id,
            agent_id=agent_id_val,
            transcript=transcript,
            index=i,
            total=total,
            semaphore=semaphore,
        )
        for i, (call_id, agent_id_val, transcript, _) in enumerate(call_data, 1)
    ]

    results = await asyncio.gather(*tasks)
    succeeded = sum(1 for r in results if r)
    failed = total - succeeded
    elapsed = time.monotonic() - t0

    print(
        f"\nDone: {succeeded} succeeded, {failed} failed out of {total} calls "
        f"in {elapsed:.1f}s ({elapsed / max(total, 1):.1f}s/call avg)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill post-call extraction")
    parser.add_argument(
        "--dry-run", action="store_true", help="List calls without processing"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max number of calls to process"
    )
    parser.add_argument(
        "--agent-id", type=str, default=None, help="Only process calls for this agent"
    )
    parser.add_argument(
        "--concurrency", type=int, default=5,
        help="Number of parallel LLM calls (default: 5)",
    )
    args = parser.parse_args()

    aid = UUID(args.agent_id) if args.agent_id else None
    asyncio.run(backfill(
        dry_run=args.dry_run,
        limit=args.limit,
        agent_id=aid,
        concurrency=args.concurrency,
    ))


if __name__ == "__main__":
    main()
