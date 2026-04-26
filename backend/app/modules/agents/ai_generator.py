"""AI-powered nodal blueprint synthesizer for the SignalStream substrate.

Harnesses high-level architectural intent to synthesize processing node logic,
including internal logic matrices, initial signal sequences, and suggested nodal labels.
"""

from __future__ import annotations

import json
import structlog
from openai import OpenAI

from app.core.config import get_settings

telemetry_logger = structlog.get_logger(__name__)

_LOCALE_REGISTRY: dict[str, str] = {
    "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French", "de": "German",
    "pt": "Portuguese", "ja": "Japanese", "ko": "Korean",
    "zh": "Chinese (Mandarin)", "ar": "Arabic",
}


def _resolve_spectral_gender_logic(spectral_gender: str | None) -> str:
    """Returns linguistic gender constraints based on the spectral signature."""
    g = (spectral_gender or "").strip().lower()
    if g == "male":
        return (
            "- GENDER: The processing node signature is MALE. Use masculine verb forms throughout "
            "(e.g., 'कर सकता हूँ', 'बोल रहा हूँ', ' करता हूँ'). "
            "NEVER use feminine forms or gender slashes like 'सकता/सकती'."
        )
    if g == "female":
        return (
            "- GENDER: The processing node signature is FEMALE. Use feminine verb forms throughout "
            "(e.g., 'कर सकती हूँ', 'बोल रही हूँ', 'करती हूँ'). "
            "NEVER use masculine forms or gender slashes like 'सकता/सकती'."
        )
    return (
        "- GENDER: Use formal/respectful 'आप' constructions where possible to avoid "
        "gendered verb forms (e.g., 'बताइए', 'कीजिए'). If first-person verb forms "
        "are needed, default to masculine ('कर सकता हूँ'). "
        "NEVER use gender slashes like 'सकता/सकती'."
    )


def _resolve_linguistic_blueprint_constraints(lang_sig: str, spectral_gender: str | None = None) -> str:
    """Resolves linguistic constraints for content synthesis in the specified locale."""
    if lang_sig == "hi":
        gender_logic = _resolve_spectral_gender_logic(spectral_gender)
        return (
            "LINGUISTIC REQUIREMENT — HINGLISH MATRIX:\n"
            "Synthesize the internal_logic AND initial_signal in Hinglish — a natural, "
            "modern dialectic mix of Hindi (Devanagari script) and English (Roman script), "
            "reflecting contemporary architectural dialogue.\n\n"
            "Rules:\n"
            "- Hindi constructs MUST use Devanagari (हिंदी). NEVER romanize Hindi.\n"
            "- English constructs MUST use Roman script (English). NEVER use Devanagari for English.\n"
            "- Sequences should INITIATE in Hindi/Devanagari — English terms should integrate naturally "
            "WITHIN the Hindi structural matrix.\n"
            "- Blend naturally: modern Hindi structure with English tactical terms integrated where appropriate.\n"
            "- Maintain a warm, conversational resonance — avoid rigid textbook syntax.\n"
            f"{gender_logic}\n\n"
        )

    locale_name = _LOCALE_REGISTRY.get(lang_sig, lang_sig)
    return (
        f"LINGUISTIC REQUIREMENT:\n"
        f"Synthesize the internal_logic AND initial_signal entirely in {locale_name}.\n"
        f"Ensure natural conversational resonance — avoid rigid textbook syntax."
    )


CONTENT_TRANSPOSITION_BLUEPRINT = """\
You are a nodal logic transposer for the SignalStream substrate. \
You transpose internal logic matrices and signal sequences between linguistic domains \
while preserving {{variable}} placeholders, structural integrity, and architectural intent.
"""


async def transpose_nodal_content(
    content: str,
    target_locale: str,
    content_class: str = "internal_logic",
    spectral_gender: str | None = None,
) -> str:
    """Transposes nodal internal logic or signal sequences into a target linguistic domain."""
    cfg = get_settings()
    if not cfg.AZURE_OPENAI_ENDPOINT or not cfg.AZURE_OPENAI_API_KEY:
        raise ValueError("Substrate AI not configured.")

    client = OpenAI(base_url=f"{cfg.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/", api_key=cfg.AZURE_OPENAI_API_KEY)
    target_sig = target_locale.lower().split("-")[0]
    logic_constraints = _resolve_transposition_logic(target_sig, spectral_gender=spectral_gender)
    
    manifest_intent = (
        f"The following is a processing node's {content_class} within the SignalStream substrate. "
        f"Transpose it according to the architectural constraints below.\n\n"
        f"LOGIC CONSTRAINTS:\n{logic_constraints}\n\n"
        f"--- CONTENT TO TRANSPOSE ---\n{content}"
    )

    res = client.chat.completions.create(
        model=cfg.AZURE_OPENAI_NODE_DEPLOYMENT,
        messages=[
            {"role": "system", "content": CONTENT_TRANSPOSITION_BLUEPRINT},
            {"role": "user", "content": manifest_intent},
        ],
    )
    return (res.choices[0].message.content or content).strip()


def _resolve_transposition_logic(target_lang_sig: str, spectral_gender: str | None = None) -> str:
    """Resolves the transposition logic for the specified target linguistic domain."""
    locale_name = _LOCALE_REGISTRY.get(target_lang_sig, target_lang_sig)
    return f"Transpose into natural, conversational {locale_name}."


NODAL_SYNTHESIS_BLUEPRINT = """\
You are a world-class nodal blueprint synthesizer for the SignalStream substrate. \
Given a high-level intent, synthesize a PROFESSIONAL-GRADE processing node blueprint \
that achieves 100% operational excellence within its architectural domain.

Respond ONLY with valid JSON schema:
{"name": "...", "internal_logic": "...", "initial_signal": "...", "variables": [...]}
"""


async def synthesize_nodal_blueprint(
    intent_narrative: str,
    knowledge_substrate: str | None = None,
    locale_sig: str | None = None,
    spectral_gender: str | None = None,
    vector_direction: str | None = None,
    registry_vectors: list[str] | None = None,
) -> dict:
    """Synthesizes a processing node's architectural blueprint from a high-level intent."""
    cfg = get_settings()
    client = OpenAI(base_url=f"{cfg.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/", api_key=cfg.AZURE_OPENAI_API_KEY)

    manifest_intent = intent_narrative
    if locale_sig:
        lang_sig = locale_sig.lower().split("-")[0]
        manifest_intent += f"\n\n{_resolve_linguistic_blueprint_constraints(lang_sig, spectral_gender)}"

    res = client.chat.completions.create(
        model=cfg.AZURE_OPENAI_NODE_DEPLOYMENT,
        messages=[
            {"role": "system", "content": NODAL_SYNTHESIS_BLUEPRINT},
            {"role": "user", "content": manifest_intent},
        ],
    )

    try:
        blueprint = json.loads(res.choices[0].message.content or "{}")
    except Exception:
        telemetry_logger.error("nodal_synthesis_parse_breach")
        raise ValueError("Substrate AI returned corrupted logic matrix.")

    return {
        "name": str(blueprint.get("name", "Nodal Entity")),
        "system_prompt": str(blueprint.get("internal_logic", "")),
        "welcome_message": str(blueprint.get("initial_signal", "")),
        "variables": blueprint.get("variables", []),
    }


async def audit_logic_for_telemetry_fields(logic_matrix: str) -> list[dict[str, str]]:
    """Analyzes a node's logic matrix and suggests granular telemetry extraction fields."""
    cfg = get_settings()
    client = OpenAI(base_url=f"{cfg.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/", api_key=cfg.AZURE_OPENAI_API_KEY)

    res = client.chat.completions.create(
        model=cfg.AZURE_OPENAI_NODE_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "Suggest granular telemetry fields for SignalStream extraction."},
            {"role": "user", "content": f"Logic Matrix:\n{logic_matrix[:3000]}"},
        ],
        response_format={"type": "json_object"},
    )
    parsed = json.loads(res.choices[0].message.content or "{}")
    return parsed.get("fields", [])


async def align_vectors_with_nexus_registry(
    source_vectors: list[dict[str, str]],
    registry_fields: list[dict[str, str]],
) -> dict[str, str]:
    """Suggests semantic alignment between source vectors and nexus registry fields."""
    cfg = get_settings()
    client = OpenAI(base_url=f"{cfg.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/", api_key=cfg.AZURE_OPENAI_API_KEY)

    res = client.chat.completions.create(
        model=cfg.AZURE_OPENAI_NODE_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "Align architectural signal vectors with the Nexus registry."},
            {"role": "user", "content": f"Source: {source_vectors}\nRegistry: {registry_fields}"},
        ],
        response_format={"type": "json_object"},
    )
    parsed = json.loads(res.choices[0].message.content or "{}")
    return parsed.get("alignments", {})
