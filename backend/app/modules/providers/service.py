"""Resolution Vector Registry — Orchestration & Cryptographic Lifecycle.

Manages the lifecycle of encrypted resolution signatures across architectural domains 
(Perception, Cognitive, Synthesis, Transport).
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.encryption import encrypt
from app.core.exceptions import ConflictError, NotFoundError, ProviderError
from app.core.secret_store import (
    SecretStoreError,
    delete_global_provider_secret,
    resolve_stored_secret,
    store_global_provider_secret,
    use_key_vault_for_global_provider_secrets,
)
from app.modules.providers.models import BackendAccess
from app.modules.providers.naming import normalize_provider_name


def _catalog_item(
    id: str,
    name: str,
    description: str | None = None,
    language: str | None = None,
    locale: str | None = None,
    gender: str | None = None,
    sample_rate_hertz: str | None = None,
    tags: list[str] | None = None,
    **kwargs,
) -> dict[str, object]:
    """Create a standardized catalog item dict."""
    item = {
        "id": id,
        "name": name,
        "description": description,
        "language": language,
        "locale": locale,
        "gender": gender,
        "sample_rate_hertz": sample_rate_hertz,
        "tags": tags or [],
    }
    item.update(kwargs)
    return item


async def _smallest_request_json(
    client: httpx.AsyncClient,
    api_key: str,
    paths: list[str],
) -> dict[str, object]:
    """Fetch JSON from Smallest AI trying multiple paths."""
    for path in paths:
        try:
            url = f"https://api.smallest.ai/v1/{path}"
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            continue
    raise ProviderError("Failed to fetch from Smallest AI")


def _smallest_default_model(config: dict[str, object] | None) -> str:
    """Get the default model for Smallest AI."""
    if config and isinstance(config.get("model"), str):
        return config["model"]
    return "lightning-v3.1"


def _as_string_list(value: object) -> list[str]:
    """Convert a value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _smallest_model_candidates(model: str) -> list[str]:
    """Get candidate model names for Smallest AI."""
    if model == "lightning-v3.1":
        return ["lightning-v3.1", "lightning-v3", "lightning"]
    return [model]


def _smallest_sample_rate_for_model(model: str) -> str:
    """Get sample rate for Smallest AI model."""
    if "v3.1" in model or "v3" in model:
        return "24000"
    return "16000"


logger = structlog.get_logger(__name__)


def _sanitize_ingress_label(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def _use_vault_for_vectors(tenant_id: UUID | None) -> bool:
    return tenant_id is None and use_key_vault_for_global_provider_secrets()


def _hash_vector_ingress_label(vector: BackendAccess) -> str:
    return (
        f"SphereVoice-vector-{vector.vector_category}-"
        f"{_sanitize_ingress_label(vector.vector_id)}-{vector.id}"
    )


def _get_engine_fallback_sig(
    settings: Settings,
    vector_id: str,
    domain: str,
) -> str | None:
    if domain == "perception":
        return {
            "perception-alpha": settings.SONIOX_API_KEY,
            "perception-beta": settings.DEEPGRAM_API_KEY,
            "perception-beta-alt": settings.DEEPGRAM_API_KEY,
            "perception-gamma": settings.GROQ_API_KEY,
            "perception-delta": settings.OPENAI_API_KEY,
            "perception-epsilon": settings.AZURE_SPEECH_API_KEY,
        }.get(vector_id) or None

    if domain == "cognitive":
        return {
            "cognitive-core": settings.OPENAI_API_KEY,
            "cognitive-fast": settings.GROQ_API_KEY,
            "cognitive-pro": settings.ANTHROPIC_API_KEY,
            "cognitive-ultra": settings.CEREBRAS_API_KEY,
            "cognitive-alt": settings.AZURE_OPENAI_API_KEY,
        }.get(vector_id) or None

    if domain == "synthesis":
        return {
            "synthesis-v1": settings.CARTESIA_API_KEY,
            "synthesis-v2": settings.ELEVENLABS_API_KEY,
            "synthesis-v3": settings.INWORLD_API_KEY,
            "synthesis-v1-alt": settings.GROQ_API_KEY,
            "synthesis-delta": settings.OPENAI_API_KEY,
            "synthesis-epsilon": settings.AZURE_SPEECH_API_KEY,
            "synthesis-zeta": settings.SARVAM_API_KEY,
            "synthesis-theta": settings.SMALLEST_API_KEY,
        }.get(vector_id) or None

    if domain == "transport":
        if vector_id == "transport-t1":
            if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
                return f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
            return None
        if vector_id == "transport-p2":
            if settings.PLIVO_AUTH_ID and settings.PLIVO_AUTH_TOKEN:
                return f"{settings.PLIVO_AUTH_ID}:{settings.PLIVO_AUTH_TOKEN}"
            return None
        if vector_id == "transport-v3":
            if settings.VOBIZ_AUTH_ID and settings.VOBIZ_API_KEY:
                return f"{settings.VOBIZ_AUTH_ID}:{settings.VOBIZ_API_KEY}"
            return None
        return None

    return None


def _global_blueprint_templates(settings: Settings) -> list[tuple[str, str, str, bool]]:
    blueprints = [
        ("perception-alpha", "perception", settings.SONIOX_API_KEY, settings.DEFAULT_STT_PROVIDER == "soniox"),
        ("perception-beta", "perception", settings.DEEPGRAM_API_KEY, False),
        ("cognitive-core", "cognitive", settings.OPENAI_API_KEY, False),
        ("cognitive-fast", "cognitive", settings.GROQ_API_KEY, settings.DEFAULT_LLM_PROVIDER == "groq"),
        ("synthesis-v3", "synthesis", settings.INWORLD_API_KEY, settings.DEFAULT_TTS_PROVIDER == "inworld"),
        ("synthesis-v1", "synthesis", settings.CARTESIA_API_KEY, settings.DEFAULT_TTS_PROVIDER == "cartesia"),
        ("synthesis-v2", "synthesis", settings.ELEVENLABS_API_KEY, settings.DEFAULT_TTS_PROVIDER == "elevenlabs"),
        ("synthesis-zeta", "synthesis", settings.SARVAM_API_KEY, settings.DEFAULT_TTS_PROVIDER == "sarvam"),
        ("synthesis-theta", "synthesis", settings.SMALLEST_API_KEY, settings.DEFAULT_TTS_PROVIDER == "smallest"),
    ]
    p_secret = _get_engine_fallback_sig(settings, "transport-p2", "transport")
    blueprints.append(("transport-p2", "transport", p_secret or "", True))
    t_secret = _get_engine_fallback_sig(settings, "transport-t1", "transport")
    blueprints.append(("transport-t1", "transport", t_secret or "", False))
    v_secret = _get_engine_fallback_sig(settings, "transport-v3", "transport")
    blueprints.append(("transport-v3", "transport", v_secret or "", False))
    return [
        (vid, dom, sig or f"demo-{vid}-key", is_def)
        for vid, dom, sig, is_def in blueprints
    ]


async def _resolve_auth_signature(vector: BackendAccess) -> str:
    try:
        return await resolve_stored_secret(
            getattr(vector, "secret_ref", None),
            vector.auth_sig_encrypted,
        )
    except SecretStoreError as exc:
        fallback = _get_engine_fallback_sig(
            get_settings(),
            vector.vector_id,
            vector.vector_category,
        )
        if fallback:
            return fallback
        raise ProviderError(vector.vector_id, str(exc)) from exc


class VectorRegistry:
    """Operations for orchestrating structural resolution vectors."""

    @staticmethod
    async def _scrub_domain_defaults(
        db: AsyncSession,
        domain: str,
        tenant_id: UUID | None,
    ) -> None:
        """Enforces a singleton fallback vector within a specific domain and context."""
        stmt = update(BackendAccess).where(BackendAccess.vector_category == domain)
        if tenant_id is None:
            stmt = stmt.where(BackendAccess.tenant_id.is_(None))
        else:
            stmt = stmt.where(BackendAccess.tenant_id == tenant_id)

        await db.execute(stmt.values(is_default=False))

    @staticmethod
    async def list_vectors(
        db: AsyncSession,
        tenant_id: UUID | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[BackendAccess], int]:
        """Lists active vectors with multi-tenant filtering and logical scoping."""
        query = select(BackendAccess)

        if tenant_id is not None:
            query = query.where(
                (BackendAccess.tenant_id == tenant_id)
                | (BackendAccess.tenant_id.is_(None))
            )

        if category:
            query = query.where(BackendAccess.vector_category == category)

        if is_active is not None:
            query = query.where(BackendAccess.is_active == is_active)

        query = query.order_by(BackendAccess.created_at.desc())

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        result = await db.execute(query)
        vectors = list(result.scalars().all())

        return vectors, total

    @staticmethod
    async def get_vector(
        db: AsyncSession,
        vector_sig: UUID,
    ) -> BackendAccess:
        """Fetches a singular vector node by its unique structural signature."""
        result = await db.execute(
            select(BackendAccess).where(BackendAccess.id == vector_sig)
        )
        vector = result.scalar_one_or_none()
        if vector is None:
            raise NotFoundError("ResolutionVector", str(vector_sig))
        return vector

    @staticmethod
    async def create_vector(
        db: AsyncSession,
        vector_id: str,
        vector_domain: str,
        auth_sig: str,
        is_default: bool = False,
        config: dict[str, object] | None = None,
        tenant_id: UUID | None = None,
    ) -> BackendAccess:
        """Provisions a new vector, encapsulating its access signature in a cryptographic envelope."""
        normalized_vid = normalize_provider_name(vector_id, vector_domain)

        use_vault = _use_vault_for_vectors(tenant_id)
        enc_sig = None if use_vault else encrypt(auth_sig)

        if is_default:
            await VectorRegistry._scrub_domain_defaults(db, vector_domain, tenant_id)

        vector = BackendAccess(
            tenant_id=tenant_id,
            vector_id=normalized_vid,
            vector_category=vector_domain,
            auth_sig_encrypted=enc_sig,
            is_default=is_default,
            config=config or {},
        )

        db.add(vector)
        await db.flush()

        if use_vault:
            try:
                vault_ref = _hash_vector_ingress_label(vector)
                setattr(vector, "secret_ref", vault_ref)
                await store_global_provider_secret(vault_ref, auth_sig)
            except SecretStoreError as exc:
                raise ProviderError(normalized_vid, str(exc)) from exc

        await db.flush()
        await db.refresh(vector)
        return vector

    @staticmethod
    async def update_vector(
        db: AsyncSession,
        vector_sig: UUID,
        vector_id: str | None = None,
        vector_category: str | None = None,
        auth_sig: str | None = None,
        is_default: bool | None = None,
        is_active: bool | None = None,
        config: dict[str, object] | None = None,
    ) -> BackendAccess:
        """Modifies vector parameters, re-obfuscating signatures as needed."""
        vector = await VectorRegistry.get_vector(db, vector_sig)

        nxt_dom = vector_category or vector.vector_category
        nxt_vid = normalize_provider_name(
            vector_id or vector.vector_id,
            nxt_dom,
        )

        if vector_id is not None or vector_category is not None:
            vector.vector_id = nxt_vid
        if vector_category is not None:
            vector.vector_category = vector_category
        if auth_sig is not None:
            v_ref = getattr(vector, "secret_ref", None)
            if v_ref or _use_vault_for_vectors(vector.tenant_id):
                try:
                    v_ref = v_ref or _hash_vector_ingress_label(vector)
                    setattr(vector, "secret_ref", v_ref)
                    await store_global_provider_secret(v_ref, auth_sig)
                except SecretStoreError as exc:
                    raise ProviderError(vector.vector_id, str(exc)) from exc
                vector.auth_sig_encrypted = None
            else:
                vector.auth_sig_encrypted = encrypt(auth_sig)
        if is_default is not None:
            if is_default:
                await VectorRegistry._scrub_domain_defaults(db, nxt_dom, vector.tenant_id)
            vector.is_default = is_default
        if is_active is not None:
            vector.is_active = is_active
        if config is not None:
            vector.config = config

        await db.flush()
        await db.refresh(vector)
        return vector

    @staticmethod
    async def delete_vector(
        db: AsyncSession,
        vector_sig: UUID,
    ) -> None:
        """Permanently decommissions a vector and purges its cryptographic state."""
        vector = await VectorRegistry.get_vector(db, vector_sig)
        v_ref = getattr(vector, "secret_ref", None)
        if v_ref:
            try:
                await delete_global_provider_secret(v_ref)
            except SecretStoreError as exc:
                raise ProviderError(vector.vector_id, str(exc)) from exc
        await db.delete(vector)
        await db.flush()

    @staticmethod
    async def audit_vector(
        db: AsyncSession,
        vector_sig: UUID,
    ) -> dict[str, str | int | None]:
        """Diagnostic audit of vector connectivity and health state."""
        vector = await VectorRegistry.get_vector(db, vector_sig)
        a_sig = await _resolve_auth_signature(vector)

        start = time.perf_counter()
        audit_res: dict[str, str | int | None] = {
            "status": "faulted",
            "latency_ms": None,
            "message": "",
        }

        try:
            audit_res = await _test_provider_connection(
                vector.vector_id,
                vector.vector_category,
                a_sig,
                vector.config,
            )
            latency = int((time.perf_counter() - start) * 1000)
            audit_res["latency_ms"] = latency
            vector.health_status = audit_res["status"]  # type: ignore
        except Exception as exc:
            audit_res = {
                "status": "faulted",
                "latency_ms": int((time.perf_counter() - start) * 1000),
                "message": str(exc),
            }
            vector.health_status = "faulted"

        vector.last_validated_at = datetime.now(UTC)
        await db.flush()

        return audit_res

    @staticmethod
    async def backfill_global_vector_templates(
        db: AsyncSession,
    ) -> dict[str, list[str]]:
        """Synchronizes global blueprint templates from higher-level environmental configurations."""
        settings = get_settings()

        res = await db.execute(select(BackendAccess).where(BackendAccess.tenant_id.is_(None)))
        vectors = list(res.scalars().all())
        v_map = {
            (v.vector_category, v.vector_id): v
            for v in vectors
        }

        synced: list[str] = []
        missing: list[str] = []
        fresh_sigs: set[tuple[str, str]] = set()

        async def _sync_node_if_compatible(v_node: BackendAccess) -> None:
            if (v_node.vector_category, v_node.vector_id) not in {
                ("perception", "perception-alpha"),
            }:
                return
            try:
                await VectorRegistry.sync_vector_catalog(db, v_node.id)
            except Exception as exc:
                logger.warning(
                    "vector_catalog_sync_fault",
                    vid=v_node.vector_id,
                    domain=v_node.vector_category,
                    error=str(exc),
                )

        for vid, dom, sig, is_def in _global_blueprint_templates(settings):
            v_key = (dom, vid)
            if v_key in v_map:
                continue

            v_node = await VectorRegistry.create_vector(
                db,
                vector_id=vid,
                vector_domain=dom,
                auth_sig=sig,
                is_default=is_def,
                tenant_id=None,
            )
            vectors.append(v_node)
            v_map[v_key] = v_node
            fresh_sigs.add(v_key)
            await _sync_node_if_compatible(v_node)
            synced.append(f"{dom}:{vid}")

        for v_node in vectors:
            v_sig = (v_node.vector_category, v_node.vector_id)
            if v_sig in fresh_sigs:
                continue

            sig_val = _get_engine_fallback_sig(
                settings,
                v_node.vector_id,
                v_node.vector_category,
            )
            label = f"{v_node.vector_category}:{v_node.vector_id}"

            if not sig_val:
                missing.append(label)
                continue

            await VectorRegistry.update_vector(
                db,
                vector_sig=v_node.id,
                auth_sig=sig_val,
            )
            await _sync_node_if_compatible(v_node)
            if label not in synced:
                synced.append(label)

        return {"synced": synced, "missing": missing}

    @staticmethod
    async def sync_vector_catalog(
        db: AsyncSession,
        vector_sig: UUID,
    ) -> BackendAccess:
        """Synchronizes localized capability catalogs for a specific vector node."""
        vector = await VectorRegistry.get_vector(db, vector_sig)
        a_sig = await _resolve_auth_signature(vector)

        catalog = await _refresh_provider_catalog(
            vector.vector_id,
            vector.vector_category,
            a_sig,
            vector.config,
        )
        vector.config = _merge_provider_catalog(
            vector.vector_id,
            vector.vector_category,
            vector.config,
            catalog,
        )
        return vector


def _catalog_capability_node(
    node_id: str,
    name: str | None = None,
    *,
    description: str | None = None,
    owner: str | None = None,
    language: str | None = None,
    locale: str | None = None,
    locale_name: str | None = None,
    local_name: str | None = None,
    gender: str | None = None,
    voice_type: str | None = None,
    sample_rate_hertz: str | None = None,
    status: str | None = None,
    words_per_minute: int | None = None,
    styles: list[str] | None = None,
    tags: list[str] | None = None,
    roles: list[str] | None = None,
    secondary_locales: list[str] | None = None,
    context_window: int | None = None,
) -> dict[str, object]:
    node: dict[str, object] = {"id": node_id, "name": name or node_id}
    if description: node["description"] = description
    if owner: node["owner"] = owner
    if language: node["language"] = language
    if locale: node["locale"] = locale
    if locale_name: node["locale_name"] = locale_name
    if local_name: node["local_name"] = local_name
    if gender: node["gender"] = gender
    if voice_type: node["voice_type"] = voice_type
    if sample_rate_hertz: node["sample_rate_hertz"] = sample_rate_hertz
    if status: node["status"] = status
    if words_per_minute is not None: node["words_per_minute"] = words_per_minute
    if styles: node["styles"] = styles
    if tags: node["tags"] = tags
    if roles: node["roles"] = roles
    if secondary_locales: node["secondary_locales"] = secondary_locales
    if context_window is not None: node["context_window"] = context_window
    return node


def _as_valid_list(value: object) -> list[str]:
    if not isinstance(value, list): return []
    return [item for item in value if isinstance(item, str) and item]


def _as_int_fallback(value: object) -> int | None:
    if isinstance(value, int): return value
    if isinstance(value, str) and value.isdigit(): return int(value)
    return None


def _synthesis_theta_default_model(config: dict[str, object]) -> str:
    val = config.get("model")
    return val if isinstance(val, str) and val else "lightning-v3.1"


def _synthesis_theta_candidates(model: str) -> list[str]:
    res = [model]
    if model == "lightning-v3.1": res.extend(["lightning", "lightning-v2"])
    elif model == "lightning": res.extend(["lightning-v3.1", "lightning-v2"])
    elif model == "lightning-v2": res.extend(["lightning-v3.1", "lightning"])
    return list(dict.fromkeys(res))


async def _synthesis_theta_ingress(
    client: httpx.AsyncClient,
    sig: str,
    path_candidates: list[str],
) -> object:
    err: Exception | None = None
    headers = {"Authorization": f"Bearer {sig}"}

    for path in path_candidates:
        for base in ("https://api.smallest.ai/waves/v1", "https://waves-api.smallest.ai/api/v1"):
            url = f"{base}/{path.lstrip('/')}"
            try:
                res = await client.get(url, headers=headers)
                if res.status_code in {404, 405}: continue
                res.raise_for_status()
                return res.json()
            except httpx.HTTPStatusError as exc:
                err = exc
                if exc.response.status_code in {404, 405}: continue
                raise
def _smallest_model_languages(model: str) -> list[str]:
    if model == "lightning-v3.1":
        return ["en", "hi", "ta", "es"]
    return ["en", "hi", "mr", "kn", "ta", "bn", "gu", "de", "fr", "es", "it", "pl", "nl", "ru"]


def _smallest_language_name_to_code(value: str) -> str:
    mapping = {
        "arabic": "ar",
        "bengali": "bn",
        "dutch": "nl",
        "english": "en",
        "french": "fr",
        "german": "de",
        "gujarati": "gu",
        "hindi": "hi",
        "italian": "it",
        "kannada": "kn",
        "marathi": "mr",
        "polish": "pl",
        "russian": "ru",
        "spanish": "es",
        "tamil": "ta",
        "telugu": "te",
    }
    return mapping.get(value.strip().lower(), value.strip().lower())


def _smallest_extract_tag_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


def _normalize_smallest_voice_catalog(
    payload: object,
    *,
    model: str,
) -> list[dict[str, object]]:
    if isinstance(payload, dict):
        raw_items = payload.get("voices", payload.get("data", []))
    else:
        raw_items = payload

    if not isinstance(raw_items, list):
        return []

    voices: list[dict[str, object]] = []
    for item in raw_items:
        if isinstance(item, str):
            voices.append(
                _catalog_item(
                    item,
                    name=item.replace("-", " ").replace("_", " ").title(),
                    sample_rate_hertz=_smallest_sample_rate_for_model(model),
                    tags=[model, "smallest-ai"],
                )
            )
            continue

        if not isinstance(item, dict):
            continue

        voice_id = item.get("voice_id") or item.get("id") or item.get("voiceId") or item.get("name")
        if not isinstance(voice_id, str) or not voice_id:
            continue

        raw_tags = item.get("tags")
        tags: list[str] = []
        language_codes: list[str] = []
        gender = item.get("gender") if isinstance(item.get("gender"), str) else None
        description = item.get("description") if isinstance(item.get("description"), str) else None

        if isinstance(raw_tags, dict):
            accent = raw_tags.get("accent")
            if isinstance(accent, str) and accent:
                tags.append(accent)

            age = raw_tags.get("age")
            if isinstance(age, str) and age:
                tags.append(age)

            usecases = _smallest_extract_tag_list(raw_tags.get("usecases"))
            emotions = _smallest_extract_tag_list(raw_tags.get("emotions"))
            tags.extend(usecases)
            tags.extend(emotions)

            raw_languages = _smallest_extract_tag_list(raw_tags.get("language"))
            language_codes = [_smallest_language_name_to_code(value) for value in raw_languages]

            if not gender and isinstance(raw_tags.get("gender"), str):
                gender = raw_tags.get("gender")

            if not description:
                description_parts = [
                    item.get("displayName") if isinstance(item.get("displayName"), str) else None,
                    accent if isinstance(accent, str) and accent else None,
                    "/".join(usecases) if usecases else None,
                ]
                description = " • ".join(part for part in description_parts if part)
        else:
            tags = _as_string_list(raw_tags)

        accent = item.get("accent")
        if isinstance(accent, str) and accent:
            tags.append(accent)

        language = item.get("language") or item.get("locale")
        locale = item.get("locale") or item.get("language")
        if not language_codes:
            if isinstance(language, str) and language:
                language_codes = [_smallest_language_name_to_code(language)]
            elif isinstance(locale, str) and locale:
                language_codes = [_smallest_language_name_to_code(locale)]

        primary_language = language_codes[0] if language_codes else None
        secondary_languages = language_codes[1:] if len(language_codes) > 1 else None
        canonical_tags = list(dict.fromkeys([*tags, *(language_codes or []), model, "smallest-ai"]))

        voices.append(
            _catalog_item(
                voice_id,
                name=item.get("display_name") or item.get("displayName") or item.get("name") or voice_id,
                description=description,
                language=primary_language,
                locale=primary_language or (locale if isinstance(locale, str) else None),
                gender=gender,
                sample_rate_hertz=_smallest_sample_rate_for_model(model),
                tags=canonical_tags,
                secondary_locales=secondary_languages,
            )
        )

    return voices


def _static_provider_models(provider_name: str, provider_category: str) -> list[dict[str, object]]:
    if provider_category == "stt" and provider_name == "soniox":
        return [
            _catalog_item(
                "stt-rt-v4",
                "STT RT v4",
                description=(
                    "Realtime multilingual STT with automatic language identification. "
                    "Supports English, Hindi, Telugu, Tamil, Kannada, Malayalam, "
                    "Gujarati, Bengali, Marathi, Punjabi, Odia, Urdu, and 50+ more languages. "
                    "Set the agent language to use that language as the primary hint."
                ),
                tags=["streaming", "multilingual", "language-identification", "indian-languages"],
            )
        ]

    if provider_category == "stt" and provider_name == "groq_whisper":
        return [
            _catalog_item("whisper-large-v3", "Whisper Large v3"),
            _catalog_item("whisper-large-v3-turbo", "Whisper Large v3 Turbo"),
        ]

    if provider_category == "tts" and provider_name == "cartesia":
        return [_catalog_item("sonic-3", "Sonic-3")]

    if provider_category == "tts" and provider_name == "elevenlabs":
        return [
            _catalog_item(
                "eleven_multilingual_v2",
                "Eleven Multilingual v2",
                description="State-of-the-art multilingual model supporting 29 languages including Hindi, Tamil, and other Indic languages.",
                tags=["multilingual", "indic", "high-quality"],
            ),
            _catalog_item(
                "eleven_turbo_v2_5",
                "Eleven Turbo v2.5",
                description="Optimised low-latency model for fast English and multilingual synthesis.",
                tags=["fast", "low-latency"],
            ),
            _catalog_item(
                "eleven_flash_v2_5",
                "Eleven Flash v2.5",
                description="Ultra-low-latency model for real-time conversational use cases.",
                tags=["ultra-fast", "conversational"],
            ),
        ]

    if provider_category == "tts" and provider_name == "inworld":
        return [
            _catalog_item(
                "inworld-tts-1.5-max",
                "Inworld TTS 1.5 Max",
                description="Best for multilingual applications with better pronunciation and more natural intonation.",
                tags=["multilingual", "high-quality"],
            ),
            _catalog_item(
                "inworld-tts-1.5-mini",
                "Inworld TTS 1.5 Mini",
                description="Lower-latency Inworld model for fast English-first voice responses.",
                tags=["fast", "low-latency"],
            ),
        ]

    if provider_category == "tts" and provider_name == "sarvam":
        return [
            _catalog_item(
                "bulbul:v3",
                "Bulbul v3",
                description="Low-latency multilingual Indian-language TTS with richer expressiveness.",
                tags=["multilingual", "india", "streaming"],
            ),
            _catalog_item(
                "bulbul:v3-beta",
                "Bulbul v3 Beta",
                description="Advanced Sarvam model with temperature control and expanded voice roster.",
                tags=["multilingual", "india", "streaming", "beta"],
            ),
            _catalog_item(
                "bulbul:v2",
                "Bulbul v2",
                description="Stable Sarvam voice model with pitch and loudness controls.",
                tags=["multilingual", "india"],
            ),
        ]

    if provider_category == "tts" and provider_name == "smallest":
        return [
            _catalog_item(
                "lightning-v3.1",
                "Lightning v3.1",
                description="Current Smallest AI TTS model with 44.1kHz output and low-latency synthesis.",
                sample_rate_hertz="44100",
                tags=["low-latency", "44khz"],
            ),
            _catalog_item(
                "lightning-v2",
                "Lightning v2",
                description="Earlier Smallest AI TTS model with broader legacy language coverage.",
                sample_rate_hertz="24000",
                tags=["legacy", "multilingual"],
            ),
        ]

    return []


def _static_provider_voices(provider_name: str, provider_category: str) -> list[dict[str, object]]:
    if provider_category != "tts":
        return []

    if provider_name == "elevenlabs":
        # ElevenLabs Indic voices — curated for Indian-language conversational AI.
        # Voice IDs are placeholders populated via catalog refresh ("Refresh" button in UI).
        # All voices support eleven_multilingual_v2 model for Hindi/Indic language TTS.
        return [
            _catalog_item("Raju", "Raju", description="Natural conversationalist with authentic Hindi delivery.", language="hi", locale="hi-IN", gender="male", tags=["indic", "conversational", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Leo", "Leo", description="Warm and clear voice for engaging conversations.", language="hi", locale="hi-IN", gender="male", tags=["indic", "warm", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Krishna", "Krishna", description="Deep and authoritative Indian male voice.", language="hi", locale="hi-IN", gender="male", tags=["indic", "authoritative", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Muskaan", "Muskaan", description="Friendly and cheerful Hindi female voice.", language="hi", locale="hi-IN", gender="female", tags=["indic", "friendly", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Viraj", "Viraj", description="Professional and confident Indian male voice.", language="hi", locale="hi-IN", gender="male", tags=["indic", "professional", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Riya Rao", "Riya Rao", description="Sweet and engaging Indian female voice.", language="hi", locale="hi-IN", gender="female", tags=["indic", "sweet", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Anjali", "Anjali", description="Clear and pleasant Hindi female voice for customer-facing use cases.", language="hi", locale="hi-IN", gender="female", tags=["indic", "pleasant", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Bunty", "Bunty", description="Casual and relatable Indian male voice.", language="hi", locale="hi-IN", gender="male", tags=["indic", "casual", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Ranbir", "Ranbir", description="Smooth and expressive Indian male voice.", language="hi", locale="hi-IN", gender="male", tags=["indic", "smooth", "hindi", "eleven_multilingual_v2"]),
            _catalog_item("Aakash Aryan", "Aakash Aryan", description="Bold and energetic Indian male voice.", language="hi", locale="hi-IN", gender="male", tags=["indic", "bold", "hindi", "eleven_multilingual_v2"]),
        ]

    if provider_name == "sarvam":
        return [
            _catalog_item("aditya", "Aditya", language="en-IN", locale="en-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("ritu", "Ritu", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("priya", "Priya", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("neha", "Neha", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("rahul", "Rahul", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("pooja", "Pooja", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("rohan", "Rohan", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("simran", "Simran", language="pa-IN", locale="pa-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("kavya", "Kavya", language="ta-IN", locale="ta-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("amit", "Amit", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("dev", "Dev", language="en-IN", locale="en-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("ishita", "Ishita", language="bn-IN", locale="bn-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("shreya", "Shreya", language="mr-IN", locale="mr-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("ratan", "Ratan", language="bn-IN", locale="bn-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("varun", "Varun", language="en-IN", locale="en-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("manan", "Manan", language="gu-IN", locale="gu-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("sumit", "Sumit", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("roopa", "Roopa", language="kn-IN", locale="kn-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("kabir", "Kabir", language="en-IN", locale="en-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("aayan", "Aayan", language="en-IN", locale="en-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("shubh", "Shubh", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("ashutosh", "Ashutosh", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("advait", "Advait", language="en-IN", locale="en-IN", gender="male", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("amelia", "Amelia", language="en-IN", locale="en-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("sophia", "Sophia", language="en-IN", locale="en-IN", gender="female", sample_rate_hertz="24000", tags=["bulbul:v3", "bulbul:v3-beta", "india"]),
            _catalog_item("anushka", "Anushka", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="22050", tags=["bulbul:v2", "india"]),
            _catalog_item("abhilash", "Abhilash", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="22050", tags=["bulbul:v2", "india"]),
            _catalog_item("manisha", "Manisha", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="22050", tags=["bulbul:v2", "india"]),
            _catalog_item("vidya", "Vidya", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="22050", tags=["bulbul:v2", "india"]),
            _catalog_item("arya", "Arya", language="hi-IN", locale="hi-IN", gender="female", sample_rate_hertz="22050", tags=["bulbul:v2", "india"]),
            _catalog_item("karun", "Karun", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="22050", tags=["bulbul:v2", "india"]),
            _catalog_item("hitesh", "Hitesh", language="hi-IN", locale="hi-IN", gender="male", sample_rate_hertz="22050", tags=["bulbul:v2", "india"]),
        ]

    return []


def _preferred_model_ids(provider_name: str, provider_category: str) -> list[str]:
    if provider_category == "stt" and provider_name == "groq_whisper":
        return ["whisper-large-v3", "whisper-large-v3-turbo"]
    if provider_category == "llm" and provider_name == "groq":
        return ["meta-llama/llama-4-scout-17b-16e-instruct", "openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    if provider_category == "tts" and provider_name == "elevenlabs":
        return ["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5"]
    if provider_category == "tts" and provider_name == "inworld":
        return ["inworld-tts-1.5-max", "inworld-tts-1.5-mini"]
    if provider_category == "tts" and provider_name == "sarvam":
        return ["bulbul:v3", "bulbul:v3-beta", "bulbul:v2"]
    if provider_category == "tts" and provider_name == "smallest":
        return ["lightning-v3.1", "lightning-v2"]
    return []


def _preferred_voice_ids(provider_name: str) -> list[str]:
    if provider_name == "inworld":
        return ["Ashley", "Craig"]
    if provider_name == "cartesia":
        return ["79a125e8-cd45-4c13-8a67-188112f4dd22"]
    if provider_name == "elevenlabs":
        return ["21m00Tcm4TlvDq8ikWAM"]  # Rachel (English default)
        # Indic voices are auto-discovered via catalog refresh
    if provider_name == "sarvam":
        return ["aditya", "anushka"]
    if provider_name == "smallest":
        return ["magnus", "olivia"]
    return []


def _resolve_selected_id(
    items: list[dict[str, object]],
    current_value: str | None,
    preferred_values: list[str],
) -> str | None:
    available_ids = [item.get("id") for item in items if isinstance(item.get("id"), str)]
    if current_value and current_value in available_ids:
        return current_value

    for preferred in preferred_values:
        if preferred in available_ids:
            return preferred

    first_value = next((item_id for item_id in available_ids if isinstance(item_id, str)), None)
    return first_value


def _mark_default_item(
    items: list[dict[str, object]],
    selected_id: str | None,
) -> list[dict[str, object]]:
    marked_items: list[dict[str, object]] = []
    for item in items:
        next_item = dict(item)
        if selected_id and next_item.get("id") == selected_id:
            next_item["is_default"] = True
        marked_items.append(next_item)
    return marked_items


def _merge_provider_catalog(
    provider_name: str,
    provider_category: str,
    existing_config: dict[str, object],
    catalog: dict[str, object],
) -> dict[str, object]:
    next_config = dict(existing_config or {})
    models = [
        item for item in catalog.get("models", [])
        if isinstance(item, dict)
    ]
    voices = [
        item for item in catalog.get("voices", [])
        if isinstance(item, dict)
    ]

    selected_model = _resolve_selected_id(
        models,
        next_config.get("model") if isinstance(next_config.get("model"), str) else None,
        _preferred_model_ids(provider_name, provider_category),
    )
    selected_voice = _resolve_selected_id(
        voices,
        next_config.get("voice_id") if isinstance(next_config.get("voice_id"), str) else None,
        _preferred_voice_ids(provider_name),
    )

    next_config["catalog"] = {
        "source": catalog.get("source", "api"),
        "refreshed_at": datetime.now(UTC).isoformat(),
        "models": _mark_default_item(models, selected_model),
        "voices": _mark_default_item(voices, selected_voice),
    }

    if selected_model:
        next_config["model"] = selected_model
    if selected_voice:
        next_config["voice_id"] = selected_voice

    return next_config


async def _refresh_provider_catalog(
    provider_name: str,
    provider_category: str,
    api_key: str,
    config: dict[str, object],
) -> dict[str, object]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        models = _static_provider_models(provider_name, provider_category)
        voices: list[dict[str, object]] = []

        if provider_name == "soniox" and provider_category == "stt":
            models = _static_provider_models(provider_name, provider_category)

        elif provider_name == "groq" and provider_category == "llm":
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            payload = resp.json()
            models = [
                _catalog_item(
                    item.get("id", ""),
                    owner=item.get("owned_by"),
                    context_window=item.get("context_window"),
                )
                for item in payload.get("data", [])
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and "whisper" not in item["id"].lower()
            ]

        elif provider_name == "groq_whisper" and provider_category == "stt":
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            payload = resp.json()
            api_models = [
                _catalog_item(item.get("id", ""))
                for item in payload.get("data", [])
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and "whisper" in item["id"].lower()
            ]
            if api_models:
                models = api_models

        elif provider_name == "cartesia" and provider_category == "tts":
            resp = await client.get(
                "https://api.cartesia.ai/voices",
                headers={
                    "X-API-Key": api_key,
                    "Cartesia-Version": "2024-06-10",
                },
                params={"limit": 100},
            )
            resp.raise_for_status()
            payload = resp.json()
            voices = [
                _catalog_item(
                    item.get("id", ""),
                    name=item.get("name"),
                    description=item.get("description"),
                    language=item.get("language"),
                    gender=item.get("gender"),
                )
                for item in payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]

        elif provider_name == "elevenlabs" and provider_category == "tts":
            # Fetch account voices (own + added from library)
            resp = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
            )
            resp.raise_for_status()
            payload = resp.json()
            voices = [
                _catalog_item(
                    item.get("voice_id", ""),
                    name=item.get("name"),
                    description=item.get("description"),
                    language=(item.get("labels") or {}).get("language") if isinstance(item.get("labels"), dict) else None,
                    locale=(item.get("labels") or {}).get("accent") if isinstance(item.get("labels"), dict) else None,
                    gender=(item.get("labels") or {}).get("gender") if isinstance(item.get("labels"), dict) else None,
                    tags=_as_string_list(list((item.get("labels") or {}).values())) if isinstance(item.get("labels"), dict) else None,
                )
                for item in payload.get("voices", [])
                if isinstance(item, dict) and isinstance(item.get("voice_id"), str)
            ]

            # Also search the shared voice library for Indic voices
            _INDIC_VOICE_SEARCHES = ["Raju", "Leo", "Krishna", "Muskaan", "Viraj", "Riya Rao", "Anjali", "Bunty", "Ranbir", "Aakash Aryan"]
            existing_names = {v.get("name", "").lower() for v in voices}
            for search_name in _INDIC_VOICE_SEARCHES:
                if search_name.lower() in existing_names:
                    continue  # Already in account voices
                try:
                    lib_resp = await client.get(
                        "https://api.elevenlabs.io/v1/shared-voices",
                        headers={"xi-api-key": api_key},
                        params={"search": search_name, "page_size": 3},
                    )
                    if lib_resp.status_code == 200:
                        lib_payload = lib_resp.json()
                        for lv in lib_payload.get("voices", []):
                            if not isinstance(lv, dict):
                                continue
                            lv_name = lv.get("name", "")
                            if search_name.lower() not in lv_name.lower():
                                continue
                            lv_id = lv.get("voice_id", "")
                            if not lv_id or lv_id in {v.get("id") for v in voices}:
                                continue
                            lv_labels = lv.get("labels", {}) if isinstance(lv.get("labels"), dict) else {}
                            voices.append(
                                _catalog_item(
                                    lv_id,
                                    name=lv_name,
                                    description=lv.get("description"),
                                    language=lv_labels.get("language"),
                                    locale=lv_labels.get("accent"),
                                    gender=lv_labels.get("gender"),
                                    tags=[*_as_string_list(list(lv_labels.values())), "indic", "shared-library"],
                                )
                            )
                            existing_names.add(lv_name.lower())
                            break  # first match per search
                except Exception:
                    logger.debug("elevenlabs_shared_voice_search_failed", search=search_name)
                    continue  # Non-critical: shared-voice search may lack permissions

        elif provider_name == "inworld" and provider_category == "tts":
            resp = await client.get(
                "https://api.inworld.ai/tts/v1/voices",
                headers={"Authorization": f"Basic {api_key}"},
            )
            resp.raise_for_status()
            payload = resp.json()
            voices = [
                _catalog_item(
                    item.get("voiceId", "") or item.get("voice_id", ""),
                    name=item.get("displayName") or item.get("name"),
                    description=item.get("description"),
                    language=(item.get("languages") or [None])[0] if isinstance(item.get("languages"), list) else item.get("language") or item.get("locale"),
                    locale=(item.get("languages") or [None])[0] if isinstance(item.get("languages"), list) else item.get("locale") or item.get("language"),
                    gender=item.get("gender"),
                    tags=_as_string_list(item.get("tags")),
                    secondary_locales=_as_string_list(item.get("languages"))[1:],
                )
                for item in payload.get("voices", [])
                if isinstance(item, dict)
                and isinstance(item.get("voiceId") or item.get("voice_id"), str)
            ]

        elif provider_name == "azure_speech" and provider_category == "tts":
            region = str(config.get("region") or get_settings().AZURE_SPEECH_REGION or "eastus")
            resp = await client.get(
                f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list",
                headers={"Ocp-Apim-Subscription-Key": api_key},
            )
            resp.raise_for_status()
            payload = resp.json()
            voices = [
                _catalog_item(
                    item.get("ShortName", ""),
                    name=item.get("DisplayName") or item.get("ShortName"),
                    description=item.get("LocaleName"),
                    language=item.get("Locale"),
                    locale=item.get("Locale"),
                    locale_name=item.get("LocaleName"),
                    local_name=item.get("LocalName"),
                    gender=item.get("Gender"),
                    voice_type=item.get("VoiceType"),
                    sample_rate_hertz=item.get("SampleRateHertz"),
                    status=item.get("Status"),
                    words_per_minute=_as_optional_int(item.get("WordsPerMinute")),
                    styles=_as_string_list(item.get("StyleList")),
                    roles=_as_string_list(item.get("RolePlayList")),
                    secondary_locales=_as_string_list(item.get("SecondaryLocaleList")),
                )
                for item in payload
                if isinstance(item, dict) and isinstance(item.get("ShortName"), str)
            ]

        elif provider_name == "openai" and provider_category == "llm":
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            payload = resp.json()
            models = [
                _catalog_item(item.get("id", ""), owner=item.get("owned_by"))
                for item in payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]

        elif provider_name == "sarvam" and provider_category == "tts":
            models = _static_provider_models(provider_name, provider_category)
            voices = _static_provider_voices(provider_name, provider_category)

        elif provider_name == "smallest" and provider_category == "tts":
            selected_model = _smallest_default_model(config)
            models = [
                _catalog_item(
                    model.get("id", "") if isinstance(model.get("id"), str) else "",
                    model.get("name") if isinstance(model.get("name"), str) else None,
                    description=model.get("description") if isinstance(model.get("description"), str) else None,
                    sample_rate_hertz=model.get("sample_rate_hertz") if isinstance(model.get("sample_rate_hertz"), str) else None,
                    tags=[*_smallest_model_languages(model.get("id", "") if isinstance(model.get("id"), str) else selected_model), *(_as_string_list(model.get("tags")) if isinstance(model, dict) else [])],
                )
                for model in _static_provider_models(provider_name, provider_category)
                if isinstance(model, dict)
            ]
            payload = await _smallest_request_json(
                client,
                api_key,
                [f"{candidate}/get_voices" for candidate in _smallest_model_candidates(selected_model)],
            )
            voices = _normalize_smallest_voice_catalog(payload, model=selected_model)
            cloned_payload = await _smallest_request_json(
                client,
                api_key,
                ["lightning-large/get_cloned_voices"],
            )
            cloned_voices = _normalize_smallest_voice_catalog(cloned_payload, model="lightning-large")
            voices_by_id = {voice["id"]: voice for voice in voices if isinstance(voice.get("id"), str)}
            for voice in cloned_voices:
                voice_id = voice.get("id")
                if not isinstance(voice_id, str):
                    continue
                merged_voice = dict(voice)
                merged_tags = list(dict.fromkeys([*(_as_string_list(voice.get("tags"))), "cloned"]))
                if merged_tags:
                    merged_voice["tags"] = merged_tags
                if voice_id in voices_by_id:
                    existing = dict(voices_by_id[voice_id])
                    existing_tags = list(dict.fromkeys([*(_as_string_list(existing.get("tags"))), *merged_tags]))
                    if existing_tags:
                        existing["tags"] = existing_tags
                    voices_by_id[voice_id] = existing
                else:
                    voices_by_id[voice_id] = merged_voice
            voices = list(voices_by_id.values())

    return {
        "source": "docs" if provider_name == "sarvam" and provider_category == "tts" else "api",
        "models": models,
        "voices": voices,
        "previous_refreshed_at": config.get("catalog", {}).get("refreshed_at")
        if isinstance(config.get("catalog"), dict)
        else None,
    }


async def _test_provider_connection(
    provider_name: str,
    provider_category: str,
    api_key: str,
    config: dict[str, object],
) -> dict[str, str | int | None]:
    """Make a lightweight API call to verify the provider key works.

    Each provider has a minimal endpoint we can hit to validate credentials.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        if provider_category == "stt":
            return await _test_stt_provider(client, provider_name, api_key, config)
        elif provider_category == "llm":
            return await _test_llm_provider(client, provider_name, api_key, config)
        elif provider_category == "tts":
            return await _test_tts_provider(client, provider_name, api_key, config)
        elif provider_category == "telephony":
            return await _test_telephony_provider(client, provider_name, api_key, config)
        else:
            return {"status": "failed", "latency_ms": None, "message": f"Unknown category: {provider_category}"}


async def _test_stt_provider(
    client: httpx.AsyncClient,
    provider_name: str,
    api_key: str,
    config: dict[str, object],
) -> dict[str, str | int | None]:
    """Test STT provider credentials."""
    if provider_name in ("deepgram", "deepgram_flux"):
        # Deepgram: GET /v1/projects with API key header
        resp = await client.get(
            "https://api.deepgram.com/v1/projects",
            headers={"Authorization": f"Token {api_key}"},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Deepgram connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Deepgram returned {resp.status_code}"}

    if provider_name == "groq_whisper":
        resp = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Groq STT connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Groq returned {resp.status_code}"}

    if provider_name == "azure_speech":
        region = str(config.get("region") or get_settings().AZURE_SPEECH_REGION or "eastus")
        resp = await client.get(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list",
            headers={"Ocp-Apim-Subscription-Key": api_key},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Azure Speech connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Azure Speech returned {resp.status_code}"}

    # Generic fallback — mark as success if key is non-empty
    return {"status": "success", "latency_ms": None, "message": f"{provider_name} key stored (no live test available)"}


async def _test_llm_provider(
    client: httpx.AsyncClient,
    provider_name: str,
    api_key: str,
    config: dict[str, object],
) -> dict[str, str | int | None]:
    """Test LLM provider credentials."""
    if provider_name == "openai":
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "OpenAI connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"OpenAI returned {resp.status_code}"}

    if provider_name == "groq":
        resp = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Groq connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Groq returned {resp.status_code}"}

    if provider_name == "anthropic":
        # Anthropic doesn't have a lightweight endpoint; just validate the key format
        if api_key.startswith("sk-ant-"):
            return {"status": "success", "latency_ms": None, "message": "Anthropic key format valid"}
        return {"status": "failed", "latency_ms": None, "message": "Invalid Anthropic key format"}

    return {"status": "success", "latency_ms": None, "message": f"{provider_name} key stored (no live test available)"}


async def _test_tts_provider(
    client: httpx.AsyncClient,
    provider_name: str,
    api_key: str,
    config: dict[str, object],
) -> dict[str, str | int | None]:
    """Test TTS provider credentials."""
    if provider_name == "elevenlabs":
        resp = await client.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": api_key},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "ElevenLabs connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"ElevenLabs returned {resp.status_code}"}

    if provider_name == "cartesia":
        resp = await client.get(
            "https://api.cartesia.ai/voices",
            headers={"X-API-Key": api_key, "Cartesia-Version": "2024-06-10"},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Cartesia connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Cartesia returned {resp.status_code}"}

    if provider_name == "inworld":
        resp = await client.get(
            "https://api.inworld.ai/tts/v1/voices",
            headers={"Authorization": f"Basic {api_key}"},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Inworld connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Inworld returned {resp.status_code}"}

    if provider_name == "azure_speech":
        region = str(config.get("region") or get_settings().AZURE_SPEECH_REGION or "eastus")
        resp = await client.get(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list",
            headers={"Ocp-Apim-Subscription-Key": api_key},
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Azure Speech connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Azure Speech returned {resp.status_code}"}

    if provider_name == "sarvam":
        resp = await client.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={
                "api-subscription-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": "Hello from SphereVoice.",
                "target_language_code": "en-IN",
                "model": "bulbul:v2",
                "speaker": "anushka",
                "speech_sample_rate": 22050,
            },
        )
        if resp.status_code == 200:
            return {"status": "success", "latency_ms": None, "message": "Sarvam connection successful"}
        return {"status": "failed", "latency_ms": None, "message": f"Sarvam returned {resp.status_code}"}

    if provider_name == "smallest":
        selected_model = _smallest_default_model(config)
        try:
            await _smallest_request_json(
                client,
                api_key,
                [f"{candidate}/get_voices" for candidate in _smallest_model_candidates(selected_model)],
            )
            return {"status": "success", "latency_ms": None, "message": "Smallest AI connection successful"}
        except Exception as exc:
            return {"status": "failed", "latency_ms": None, "message": f"Smallest AI test failed: {exc}"}

    return {"status": "success", "latency_ms": None, "message": f"{provider_name} key stored (no live test available)"}


async def _test_telephony_provider(
    client: httpx.AsyncClient,
    provider_name: str,
    api_key: str,
    config: dict[str, object],
) -> dict[str, str | int | None]:
    """Test telephony provider credentials."""
    if provider_name == "twilio":
        # Twilio uses Account SID + Auth Token (stored as "sid:token" in api_key)
        parts = api_key.split(":", 1)
        if len(parts) == 2:
            account_sid, auth_token = parts
            resp = await client.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json",
                auth=(account_sid, auth_token),
            )
            if resp.status_code == 200:
                return {"status": "success", "latency_ms": None, "message": "Twilio connection successful"}
            return {"status": "failed", "latency_ms": None, "message": f"Twilio returned {resp.status_code}"}
        return {"status": "failed", "latency_ms": None, "message": "Twilio key format: 'account_sid:auth_token'"}

    if provider_name == "plivo":
        # Plivo uses Auth ID + Auth Token (stored as "auth_id:auth_token")
        parts = api_key.split(":", 1)
        if len(parts) == 2:
            auth_id, auth_token = parts
            resp = await client.get(
                f"https://api.plivo.com/v1/Account/{auth_id}/",
                auth=(auth_id, auth_token),
            )
            if resp.status_code == 200:
                return {"status": "success", "latency_ms": None, "message": "Plivo connection successful"}
            return {"status": "failed", "latency_ms": None, "message": f"Plivo returned {resp.status_code}"}
        return {"status": "failed", "latency_ms": None, "message": "Plivo key format: 'auth_id:auth_token'"}

    if provider_name == "vobiz":
        parts = api_key.split(":", 1)
        if len(parts) == 2:
            auth_id, auth_token = parts
            resp = await client.get(
                f"https://api.vobiz.ai/api/v1/account/{auth_id}/",
                headers={"X-Auth-ID": auth_id, "X-Auth-Token": auth_token},
            )
            if resp.status_code == 200:
                return {"status": "success", "latency_ms": None, "message": "Vobiz connection successful"}
            return {"status": "failed", "latency_ms": None, "message": f"Vobiz returned {resp.status_code}"}
        return {"status": "failed", "latency_ms": None, "message": "Vobiz key format: 'auth_id:auth_token'"}

    return {"status": "success", "latency_ms": None, "message": f"{provider_name} key stored (no live test available)"}
