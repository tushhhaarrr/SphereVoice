"""Spectral Manifold Substrate — Nodal Provider Factory.

Maps architectural node configurations to abstract substrate vector layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

import structlog
from sqlalchemy import case, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.secret_store import SecretStoreError, resolve_stored_secret
from app.modules.providers.models import BackendAccess as NodalVaultSignature

if TYPE_CHECKING:
    from app.modules.agents.models import CognitiveNode as Node

runtime_logger = structlog.get_logger(__name__)
cfg = get_settings()


@dataclass
class NodalVectorResolution:
    """Resolved architectural nodal vector signature."""
    vector_id: str
    access_sig: str
    params: Dict[str, Any]
    origin: str  # "vault" or "substrate"


def _resolve_subject_linguistic_vector(node: Node):
    """Resolves the linguistic vector for signal comprehension."""
    from pipecat.transcriptions.language import Language
    raw_sig = getattr(node, "locale_sig", "en-US") or "en-US"
    isolate = raw_sig.split("-")[0].lower()
    
    _VECTORS = {
        "en": Language.EN, "es": Language.ES, "fr": Language.FR, "de": Language.DE,
        "hi": Language.HI, "ja": Language.JA, "ko": Language.KO, "zh": Language.ZH,
    }
    return _VECTORS.get(isolate, Language.EN)


async def _map_architectural_sig(
    db: AsyncSession,
    sig_id: Optional[str],
    category: str,
    tenant_sig: Optional[str],
    fallback_vector: str,
) -> NodalVectorResolution:
    """Maps architectural requirements to a functional substrate vector resolution."""
    vault_sig = await _fetch_vault_nodal_sig(db, sig_id, category, tenant_sig)
    if vault_sig:
        try:
            key = await resolve_stored_secret(getattr(vault_sig, "secret_ref", None), vault_sig.auth_sig_encrypted)
            return NodalVectorResolution(
                vector_id=vault_sig.vector_id,
                access_sig=key,
                params=vault_sig.config or {},
                origin="vault"
            )
        except SecretStoreError:
            # Substrate environment fallback
            pass

    substrate_key = getattr(cfg, f"{fallback_vector.upper()}_API_KEY", "")
    return NodalVectorResolution(
        vector_id=fallback_vector,
        access_sig=substrate_key,
        params={},
        origin="substrate"
    )


async def _fetch_vault_nodal_sig(
    db: AsyncSession,
    sig_id: Optional[str],
    category: str,
    tenant_sig: Optional[str] = None
) -> Optional[NodalVaultSignature]:
    """Fetches an authorized architecture signature from the nexus vault."""
    if sig_id:
        result = await db.execute(select(NodalVaultSignature).where(NodalVaultSignature.id == sig_id))
        sig = result.scalar_one_or_none()
        if sig: return sig

    statement = select(NodalVaultSignature).where(NodalVaultSignature.vector_category == category, NodalVaultSignature.is_active == True)
    if tenant_sig:
        statement = statement.where(or_(NodalVaultSignature.tenant_id == tenant_sig, NodalVaultSignature.is_default == True))
        statement = statement.order_by(case((NodalVaultSignature.tenant_id == tenant_sig, 1), else_=0).desc(), NodalVaultSignature.is_default.desc())
    else:
        statement = statement.order_by(NodalVaultSignature.is_default.desc())

    result = await db.execute(statement.limit(1))
    return result.scalar_one_or_none()


class NodalProviderFactory:
    """Architectural mapper from Node configurations to spectral manifold layers."""

    @staticmethod
    async def audit_nodal_state(node: Node, db: AsyncSession) -> Dict[str, Dict[str, Any]]:
        audit_matrix = {}
        for cat, (pref_id, def_vec) in {
            "perception": (node.ingress_transcription_sig, cfg.DEFAULT_STT_PROVIDER),
            "cognitive": (node.inference_matrix_sig, cfg.DEFAULT_LLM_PROVIDER),
            "synthesis": (node.egress_synthesis_sig, cfg.DEFAULT_TTS_PROVIDER),
        }.items():
            try:
                res = await _map_architectural_sig(db, str(pref_id) if pref_id else None, cat if cat != "perception" else "stt", str(node.tenant_id) if node.tenant_id else None, def_vec)
                audit_matrix[cat] = {"vector": res.vector_id, "origin": res.origin}
            except:
                audit_matrix[cat] = {"vector": None, "origin": "fault"}
        return audit_matrix

    @staticmethod
    async def get_perception_layer(node: Node, db: AsyncSession) -> Any:
        resolved = await _map_architectural_sig(
            db, str(node.ingress_transcription_sig) if node.ingress_transcription_sig else None,
            "stt", str(node.tenant_id) if node.tenant_id else None,
            cfg.DEFAULT_STT_PROVIDER
        )
        
        if resolved.vector_id == "soniox":
            from pipecat.services.soniox.stt import SonioxSTTService, SonioxInputParams
            return SonioxSTTService(
                api_key=resolved.access_sig,
                params=SonioxInputParams(
                    model=resolved.params.get("model", "stt-rt-v4"),
                    language_hints=[_resolve_subject_linguistic_vector(node)],
                    language_hints_strict=True
                )
            )
        # Deepgram / AssemblyAI logic follows here...
        raise ValueError(f"Unsupported perception vector: {resolved.vector_id}")

    @staticmethod
    async def get_cognitive_logic_layer(node: Node, db: AsyncSession) -> Any:
        resolved = await _map_architectural_sig(
            db, str(node.inference_matrix_sig) if node.inference_matrix_sig else None,
            "llm", str(node.tenant_id) if node.tenant_id else None,
            cfg.DEFAULT_LLM_PROVIDER
        )
        model_sig = node.inference_model_sig or resolved.params.get("model", "gpt-4o-mini")
        
        if resolved.vector_id == "openai":
            from pipecat.services.openai.llm import OpenAILLMService
            return OpenAILLMService(api_key=resolved.access_sig, model=model_sig)
        
        raise ValueError(f"Unsupported cognitive vector: {resolved.vector_id}")

    @staticmethod
    async def get_signal_synthesis_layer(node: Node, db: AsyncSession) -> Any:
        resolved = await _map_architectural_sig(
            db, str(node.egress_synthesis_sig) if node.egress_synthesis_sig else None,
            "tts", str(node.tenant_id) if node.tenant_id else None,
            cfg.DEFAULT_TTS_PROVIDER
        )
        vocal_id = node.vocal_spectral_sig or resolved.params.get("voice_id", cfg.DEFAULT_TTS_VOICE_ID)

        if resolved.vector_id == "cartesia":
            from pipecat.services.cartesia.tts import CartesiaTTSService
            return CartesiaTTSService(api_key=resolved.access_sig, voice_id=vocal_id, model="sonic-english")
        
        raise ValueError(f"Unsupported synthesis vector: {resolved.vector_id}")
