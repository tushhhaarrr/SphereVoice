"""Architectural Substrate — Retrospective signal analysis and abstraction.

Extracts structured insights from a lexical chronicle after synchronisation
termination using the configured cognitive layer.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.calls.service import VoiceEngineService
from app.modules.pipeline.extraction_templates import extract_cognitive_vectors as resolve_extraction_fields

logger = structlog.get_logger(__name__)
settings = get_settings()

# Maximum chronicle characters sent to the cognitive layer
_MAX_CHRONICLE_CHARS = 24_000

# Abstraction version
_ABSTRACTION_VERSION = "3.0_SIGNALSTREAM"

_ANALYSIS_SYSTEM_BLUEPRINT = (
    "You are an expert SignalStream synchronisation analyst. Your objective is to "
    "distill structural insights from lexical chronicles with architectural precision. "
    "Respond with valid JSON manifestations only."
)


async def run_post_synchronisation_analysis(
    db: AsyncSession,
    sync_sig: UUID,
    processing_node: object,
    lexical_chronicle: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract structured insights from a lexical chronicle using the cognitive layer.

    Resolves abstraction fields from nodal config, builds a dynamic analysis prompt,
    calls the cognitive substrate, and persists results to the architectural registry.
    """
    abstraction_fields = resolve_extraction_fields(processing_node)
    if not abstraction_fields or not lexical_chronicle:
        return {}

    chronicle_text = _format_lexical_chronicle(lexical_chronicle)
    analysis_prompt = build_retrospective_analysis_prompt(abstraction_fields, lexical_chronicle)
    if not analysis_prompt:
        return {}

    try:
        abstracted_manifest, provider_used = await _invoke_cognitive_layer_for_abstraction(processing_node, analysis_prompt, chronicle_text)
    except Exception:
        logger.warning("retrospective_abstraction_fault", sync_sig=str(sync_sig), exc_info=True)
        return {}

    # Append architectural metadata
    abstracted_manifest["_abstraction_version"] = _ABSTRACTION_VERSION
    abstracted_manifest["_abstracted_at"] = datetime.now(UTC).isoformat()
    abstracted_manifest["_cognitive_provider"] = provider_used

    # Persist abstracted manifest to the substrate
    await VoiceEngineService.update_call(
        session_store=db,
        call_id=sync_sig,
        summary=abstracted_manifest,
        summary_finalized_at=datetime.now(UTC),
    )
    await db.flush()

    logger.info("retrospective_analysis_quiesced", sync_sig=str(sync_sig))
    return abstracted_manifest


def build_retrospective_analysis_prompt(
    fields: list[dict[str, str]],
    chronicle: list[dict[str, Any]],
) -> str:
    """Synthesize the cognitive layer analysis prompt from resolved fields and chronicle."""
    if not fields:
        return ""

    chronicle_text = _format_lexical_chronicle(chronicle)
    if not chronicle_text.strip():
        return ""

    if len(chronicle_text) > _MAX_CHRONICLE_CHARS:
        chronicle_text = chronicle_text[:_MAX_CHRONICLE_CHARS] + "\n... [CHRONICLE TRUNCATED]"

    field_manifest = [f'- "{f.get("name")}" ({f.get("type", "string")}): {f.get("description")}' for f in fields if f.get("name")]
    if not field_manifest:
        return ""

    return (
        "Analyze the SignalStream chronicle below and distill the requested manifestations.\n\n"
        "## Structural Manifestations\n" + "\n".join(field_manifest) + "\n\n"
        "## Lexical Chronicle\n" + chronicle_text
    )


def _format_lexical_chronicle(chronicle: list[dict[str, Any]]) -> str:
    """Format chronicle turns into structured text for cognitive ingestion."""
    return "\n".join(f"{e.get('speaker', 'unknown')}: {e.get('text', '')}" for e in chronicle if e.get("text"))


async def _invoke_cognitive_layer_for_abstraction(
    node: object,
    prompt: str,
    chronicle_text: str = "",
) -> tuple[dict[str, Any], str]:
    """Invoke the cognitive layer substrate to distill structured insights."""
    try:
        manifest = await _attempt_azure_openai_abstraction(prompt)
        if manifest:
            return manifest, "azure_openai"
    except Exception:
        logger.warning("abstraction_layer_fault")
    
    return {"status": "quiesced"}, "fallback_vector"


async def _attempt_azure_openai_abstraction(prompt: str) -> dict[str, Any] | None:
    endpoint = settings.AZURE_OPENAI_ENDPOINT
    api_key = settings.AZURE_OPENAI_API_KEY
    if not endpoint or not api_key:
        return None

    deployment = settings.AZURE_OPENAI_NODE_DEPLOYMENT
    api_version = settings.AZURE_OPENAI_API_VERSION
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "messages": [
                    {"role": "system", "content": _ANALYSIS_SYSTEM_BLUEPRINT},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        payload = resp.json()

    raw_manifest = payload.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    return json.loads(raw_manifest)
