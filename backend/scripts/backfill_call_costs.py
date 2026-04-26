"""Backfill call costs — recalculate from usage_metrics for all calls.

Re-estimates STT seconds using VAD-aware logic (batch STT providers only process
speech segments, not full call duration), then recalculates all costs from the
current pricing table.

Run: cd backend && python3 scripts/backfill_call_costs.py
"""
import asyncio
import json
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal

import structlog

logger = structlog.get_logger(__name__)

# Batch STT providers that only process VAD-triggered speech segments
_BATCH_STT_PROVIDERS = frozenset({"groq_whisper", "openai_whisper", "sambanova"})


def _estimate_stt_seconds(
    stt_provider: str | None,
    transcript: list[dict] | None,
    call_duration: float,
) -> float:
    """Estimate STT audio seconds using the same logic as CallCostTracker."""
    if not stt_provider:
        return call_duration
    if stt_provider in _BATCH_STT_PROVIDERS and transcript:
        user_chars = sum(
            len(str(e.get("text", "")))
            for e in transcript
            if e.get("speaker") == "user" and e.get("text")
        )
        estimated = user_chars / 12.0  # ~150 WPM ≈ 12 chars/sec
        user_turns = sum(1 for e in transcript if e.get("speaker") == "user")
        return max(max(1.0, float(user_turns)), min(estimated, call_duration))
    return call_duration


async def backfill():
    from sqlalchemy import text

    from app.core.database import async_session_factory
    from app.modules.pricing.schemas import UsageMetrics
    from app.modules.pricing.service import PricingService

    async with async_session_factory() as db:
        # Process all calls with usage_metrics to fix STT duration estimates
        result = await db.execute(
            text(
                """
                SELECT id, usage_metrics, duration_seconds, transcript
                FROM calls
                WHERE usage_metrics IS NOT NULL
                  AND usage_metrics != '{}'::jsonb
                ORDER BY created_at DESC
                """
            )
        )
        rows = result.fetchall()
        print(f"Found {len(rows)} calls to process")

        updated = 0
        for call_id, metrics, duration, transcript in rows:
            if not metrics:
                continue

            stt = metrics.get("stt", {})
            llm = metrics.get("llm", {})
            tts = metrics.get("tts", {})
            tel = metrics.get("telephony", {})
            call_dur = float(duration or tel.get("duration_seconds", 0))

            # Re-estimate STT seconds with VAD-aware logic
            corrected_stt_secs = _estimate_stt_seconds(
                stt.get("provider"), transcript or [], call_dur
            )

            usage = UsageMetrics(
                stt_provider=stt.get("provider"),
                stt_model=stt.get("model"),
                stt_audio_seconds=corrected_stt_secs,
                llm_provider=llm.get("provider"),
                llm_model=llm.get("model"),
                llm_input_tokens=llm.get("input_tokens", 0),
                llm_output_tokens=llm.get("output_tokens", 0),
                tts_provider=tts.get("provider"),
                tts_model=tts.get("model"),
                tts_characters=tts.get("characters", 0),
                telephony_provider=tel.get("provider"),
                telephony_seconds=tel.get("duration_seconds", 0),
            )

            breakdown = await PricingService.calculate_costs(db, usage)

            # Also update usage_metrics with corrected STT seconds
            corrected_metrics = dict(metrics)
            if "stt" in corrected_metrics:
                corrected_metrics["stt"] = {
                    **corrected_metrics["stt"],
                    "audio_seconds": round(corrected_stt_secs, 2),
                }

            await db.execute(
                text(
                    """
                    UPDATE calls
                    SET stt_cost = :stt,
                        llm_cost = :llm,
                        tts_cost = :tts,
                        telephony_cost = :tel,
                        total_cost = :total,
                        usage_metrics = CAST(:metrics AS jsonb)
                    WHERE id = :id
                    """
                ),
                {
                    "stt": breakdown.stt_cost,
                    "llm": breakdown.llm_cost,
                    "tts": breakdown.tts_cost,
                    "tel": breakdown.telephony_cost,
                    "total": breakdown.total_cost,
                    "id": call_id,
                    "metrics": json.dumps(corrected_metrics),
                },
            )
            updated += 1
            stt_label = f"{corrected_stt_secs:.1f}s" if stt.get("provider") in _BATCH_STT_PROVIDERS else f"{call_dur:.0f}s"
            print(
                f"  {call_id}: ${breakdown.total_cost:.8f} "
                f"(STT={stt_label}=${breakdown.stt_cost:.6f} LLM=${breakdown.llm_cost:.6f} "
                f"TTS=${breakdown.tts_cost:.6f} Tel=${breakdown.telephony_cost:.6f})"
            )

        await db.commit()
        print(f"\nBackfilled {updated}/{len(rows)} calls")


if __name__ == "__main__":
    asyncio.run(backfill())
