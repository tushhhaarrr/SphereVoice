"""Unit tests for provider secret storage behavior."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.providers.models import BackendAccess
from app.modules.providers.service import VectorRegistry
from app.core.config import Settings


@pytest.mark.asyncio
async def test_create_provider_uses_vault_for_global_secret() -> None:
    """Global provider keys should be stored in Key Vault when enabled."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.modules.providers.service._use_vault_for_vectors",
            return_value=True,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
        patch("app.modules.providers.service.encrypt") as mock_encrypt,
    ):
        provider = await VectorRegistry.create_vector(
            db,
            vector_id="groq",
            vector_domain="llm",
            auth_sig="shared-groq-key",
            is_default=True,
            tenant_id=None,
        )

    mock_encrypt.assert_not_called()
    assert provider.auth_sig_encrypted is None
    assert provider.secret_ref is not None
    assert provider.secret_ref.startswith("SphereVoice-vector-llm-groq-")
    mock_store_secret.assert_awaited_once_with(provider.secret_ref, "shared-groq-key")


@pytest.mark.asyncio
async def test_create_provider_encrypts_tenant_secret() -> None:
    """Tenant-scoped provider keys should stay encrypted in the database."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.modules.providers.service._use_vault_for_vectors",
            return_value=False,
        ),
        patch(
            "app.modules.providers.service.encrypt",
            return_value="encrypted-value",
        ) as mock_encrypt,
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
    ):
        provider = await VectorRegistry.create_vector(
            db,
            vector_id="inworld",
            vector_domain="tts",
            auth_sig="tenant-tts-key",
            tenant_id=uuid.uuid4(),
            config={"voice_id": "Ashley"},
        )

    mock_encrypt.assert_called_once_with("tenant-tts-key")
    mock_store_secret.assert_not_awaited()
    assert provider.auth_sig_encrypted == "encrypted-value"
    assert provider.secret_ref is None


@pytest.mark.asyncio
async def test_update_provider_rotates_existing_vault_secret() -> None:
    """Updating a vault-managed provider should rotate the existing vault secret."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    provider = BackendAccess(
        vector_id="groq",
        vector_category="llm",
        tenant_id=None,
        auth_sig_encrypted=None,
        secret_ref="SphereVoice-provider-llm-groq-123",
        config={},
    )

    with (
        patch(
            "app.modules.providers.service.VectorRegistry.get_vector",
            new_callable=AsyncMock,
            return_value=provider,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
        patch("app.modules.providers.service.encrypt") as mock_encrypt,
    ):
        updated = await VectorRegistry.update_vector(
            db,
            vector_sig=provider.id,
            auth_sig="rotated-key",
        )

    mock_encrypt.assert_not_called()
    mock_store_secret.assert_awaited_once_with("SphereVoice-provider-llm-groq-123", "rotated-key")
    assert updated.secret_ref == "SphereVoice-provider-llm-groq-123"
    assert updated.auth_sig_encrypted is None


@pytest.mark.asyncio
async def test_delete_provider_removes_vault_secret() -> None:
    """Deleting a vault-managed provider should delete the backing secret."""
    db = AsyncMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()

    provider = BackendAccess(
        vector_id="openai",
        vector_category="llm",
        tenant_id=None,
        auth_sig_encrypted=None,
        secret_ref="SphereVoice-provider-llm-openai-123",
        config={},
    )

    with (
        patch(
            "app.modules.providers.service.VectorRegistry.get_vector",
            new_callable=AsyncMock,
            return_value=provider,
        ),
        patch(
            "app.modules.providers.service.delete_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_delete_secret,
    ):
        await VectorRegistry.delete_vector(db, provider.id)

    mock_delete_secret.assert_awaited_once_with("SphereVoice-provider-llm-openai-123")
    db.delete.assert_awaited_once_with(provider)


def test_get_platform_provider_secret_maps_twilio_credentials() -> None:
    """Twilio provider secrets should be built from SID and auth token."""
    from app.modules.providers.service import _get_engine_fallback_sig

    settings = Settings(
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="token-456",
    )

    secret = _get_engine_fallback_sig(settings, "transport-t1", "transport")

    assert secret == "AC123:token-456"


def test_get_platform_provider_secret_maps_new_tts_credentials() -> None:
    """Sarvam and Smallest AI secrets should map from settings."""
    from app.modules.providers.service import _get_engine_fallback_sig

    settings = Settings(
        SARVAM_API_KEY="sarvam-key",
        SMALLEST_API_KEY="smallest-key",
    )

    assert _get_engine_fallback_sig(settings, "synthesis-zeta", "synthesis") == "sarvam-key"
    assert _get_engine_fallback_sig(settings, "synthesis-theta", "synthesis") == "smallest-key"


@pytest.mark.asyncio
async def test_sync_shared_provider_secrets_from_settings_updates_only_configured(
    db_session: AsyncSession,
) -> None:
    """Only shared providers with configured platform credentials should be backfilled."""
    groq = BackendAccess(
        vector_id="cognitive-fast",
        vector_category="cognitive",
        tenant_id=None,
        auth_sig_encrypted="stale-groq",
        config={},
    )
    openai = BackendAccess(
        vector_id="cognitive-core",
        vector_category="cognitive",
        tenant_id=None,
        auth_sig_encrypted="stale-openai",
        config={},
    )
    db_session.add(groq)
    db_session.add(openai)
    await db_session.flush()

    with (
        patch(
            "app.modules.providers.service.get_settings",
            return_value=MagicMock(
                OPENAI_API_KEY="",
                GROQ_API_KEY="valid-groq",
            ),
        ),
        patch(
            "app.modules.providers.service._global_blueprint_templates",
            return_value=[
                ("cognitive-fast", "cognitive", "valid-groq", False),
                ("cognitive-core", "cognitive", "", False),
            ],
        ),
        patch(
            "app.modules.providers.service._use_vault_for_vectors",
            return_value=True,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
    ):
        result = await VectorRegistry.backfill_global_vector_templates(db_session)

    assert result == {
        "synced": ["cognitive:cognitive-fast"],
        "missing": ["cognitive:cognitive-core"],
    }
    assert groq.secret_ref is not None
    assert groq.secret_ref.startswith("SphereVoice-vector-cognitive-cognitive-fast-")
    assert groq.auth_sig_encrypted is None
    assert openai.secret_ref is None
    assert openai.auth_sig_encrypted == "stale-openai"
    mock_store_secret.assert_awaited_once_with(groq.secret_ref, "valid-groq")


@pytest.mark.asyncio
async def test_sync_shared_provider_secrets_from_settings_creates_missing_inworld(
    db_session: AsyncSession,
) -> None:
    """Configured shared providers missing from the DB should be created and synced."""
    with (
        patch(
            "app.modules.providers.service.get_settings",
            return_value=MagicMock(
                INWORLD_API_KEY="valid-inworld",
            ),
        ),
        patch(
            "app.modules.providers.service._global_blueprint_templates",
            return_value=[
                ("synthesis-v3", "synthesis", "valid-inworld", True),
            ],
        ),
        patch(
            "app.modules.providers.service._use_vault_for_vectors",
            return_value=True,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
    ):
        result = await VectorRegistry.backfill_global_vector_templates(db_session)

    inworld = (
        await db_session.execute(
            select(BackendAccess).where(
                BackendAccess.tenant_id.is_(None),
                BackendAccess.vector_id == "synthesis-v3",
                BackendAccess.vector_category == "synthesis",
            )
        )
    ).scalar_one()

    assert "synthesis:synthesis-v3" in result["synced"]
    assert result["missing"] == []
    assert inworld.secret_ref is not None
    assert inworld.is_default is True
    mock_store_secret.assert_awaited_once_with(inworld.secret_ref, "valid-inworld")