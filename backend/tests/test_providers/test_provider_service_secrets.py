"""Unit tests for provider secret storage behavior."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.providers.models import ProviderKey
from app.modules.providers.service import ProviderService


@pytest.mark.asyncio
async def test_create_provider_uses_vault_for_global_secret() -> None:
    """Global provider keys should be stored in Key Vault when enabled."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.modules.providers.service._should_use_vault_secret_storage",
            return_value=True,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
        patch("app.modules.providers.service.encrypt") as mock_encrypt,
    ):
        provider = await ProviderService.create_provider(
            db,
            provider_name="groq",
            provider_category="llm",
            api_key="shared-groq-key",
            is_default=True,
            tenant_id=None,
        )

    mock_encrypt.assert_not_called()
    assert provider.api_key_encrypted is None
    assert provider.secret_ref is not None
    assert provider.secret_ref.startswith("SphereVoice-provider-llm-groq-")
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
            "app.modules.providers.service._should_use_vault_secret_storage",
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
        provider = await ProviderService.create_provider(
            db,
            provider_name="inworld",
            provider_category="tts",
            api_key="tenant-tts-key",
            tenant_id=uuid.uuid4(),
            config={"voice_id": "Ashley"},
        )

    mock_encrypt.assert_called_once_with("tenant-tts-key")
    mock_store_secret.assert_not_awaited()
    assert provider.api_key_encrypted == "encrypted-value"
    assert provider.secret_ref is None


@pytest.mark.asyncio
async def test_update_provider_rotates_existing_vault_secret() -> None:
    """Updating a vault-managed provider should rotate the existing vault secret."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    provider = ProviderKey(
        provider_name="groq",
        provider_category="llm",
        tenant_id=None,
        api_key_encrypted=None,
        secret_ref="SphereVoice-provider-llm-groq-123",
        config={},
    )

    with (
        patch(
            "app.modules.providers.service.ProviderService.get_provider",
            new_callable=AsyncMock,
            return_value=provider,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
        patch("app.modules.providers.service.encrypt") as mock_encrypt,
    ):
        updated = await ProviderService.update_provider(
            db,
            provider_id=provider.id,
            api_key="rotated-key",
        )

    mock_encrypt.assert_not_called()
    mock_store_secret.assert_awaited_once_with("SphereVoice-provider-llm-groq-123", "rotated-key")
    assert updated.secret_ref == "SphereVoice-provider-llm-groq-123"
    assert updated.api_key_encrypted is None


@pytest.mark.asyncio
async def test_delete_provider_removes_vault_secret() -> None:
    """Deleting a vault-managed provider should delete the backing secret."""
    db = AsyncMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()

    provider = ProviderKey(
        provider_name="openai",
        provider_category="llm",
        tenant_id=None,
        api_key_encrypted=None,
        secret_ref="SphereVoice-provider-llm-openai-123",
        config={},
    )

    with (
        patch(
            "app.modules.providers.service.ProviderService.get_provider",
            new_callable=AsyncMock,
            return_value=provider,
        ),
        patch(
            "app.modules.providers.service.delete_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_delete_secret,
    ):
        await ProviderService.delete_provider(db, provider.id)

    mock_delete_secret.assert_awaited_once_with("SphereVoice-provider-llm-openai-123")
    db.delete.assert_awaited_once_with(provider)


def test_get_platform_provider_secret_maps_twilio_credentials() -> None:
    """Twilio provider secrets should be built from SID and auth token."""
    from app.core.config import Settings
    from app.modules.providers.service import _get_platform_provider_secret

    settings = Settings(
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="token-456",
    )

    secret = _get_platform_provider_secret(settings, "twilio", "telephony")

    assert secret == "AC123:token-456"


def test_get_platform_provider_secret_maps_new_tts_credentials() -> None:
    """Sarvam and Smallest AI secrets should map from settings."""
    from app.core.config import Settings
    from app.modules.providers.service import _get_platform_provider_secret

    settings = Settings(
        SARVAM_API_KEY="sarvam-key",
        SMALLEST_API_KEY="smallest-key",
    )

    assert _get_platform_provider_secret(settings, "sarvam", "tts") == "sarvam-key"
    assert _get_platform_provider_secret(settings, "smallest", "tts") == "smallest-key"


@pytest.mark.asyncio
async def test_sync_shared_provider_secrets_from_settings_updates_only_configured(
    db_session: AsyncSession,
) -> None:
    """Only shared providers with configured platform credentials should be backfilled."""
    groq = ProviderKey(
        provider_name="groq",
        provider_category="llm",
        tenant_id=None,
        api_key_encrypted="stale-groq",
        config={},
    )
    openai = ProviderKey(
        provider_name="openai",
        provider_category="llm",
        tenant_id=None,
        api_key_encrypted="stale-openai",
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
                DEEPGRAM_API_KEY="",
                ANTHROPIC_API_KEY="",
                CEREBRAS_API_KEY="",
                CARTESIA_API_KEY="",
                ELEVENLABS_API_KEY="",
                INWORLD_API_KEY="",
                SARVAM_API_KEY="",
                SMALLEST_API_KEY="",
                TWILIO_ACCOUNT_SID="",
                TWILIO_AUTH_TOKEN="",
            ),
        ),
        patch(
            "app.modules.providers.service._should_use_vault_secret_storage",
            return_value=True,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
    ):
        result = await ProviderService.sync_shared_provider_secrets_from_settings(db_session)

    assert result == {
        "synced": ["llm:groq"],
        "missing": ["llm:openai"],
    }
    assert groq.secret_ref is not None
    assert groq.secret_ref.startswith("SphereVoice-provider-llm-groq-")
    assert groq.api_key_encrypted is None
    assert openai.secret_ref is None
    assert openai.api_key_encrypted == "stale-openai"
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
                OPENAI_API_KEY="",
                GROQ_API_KEY="",
                DEEPGRAM_API_KEY="",
                ANTHROPIC_API_KEY="",
                CEREBRAS_API_KEY="",
                CARTESIA_API_KEY="",
                ELEVENLABS_API_KEY="",
                INWORLD_API_KEY="valid-inworld",
                SARVAM_API_KEY="",
                SMALLEST_API_KEY="",
                TWILIO_ACCOUNT_SID="",
                TWILIO_AUTH_TOKEN="",
                DEFAULT_LLM_PROVIDER="groq",
                DEFAULT_TTS_PROVIDER="inworld",
            ),
        ),
        patch(
            "app.modules.providers.service._should_use_vault_secret_storage",
            return_value=True,
        ),
        patch(
            "app.modules.providers.service.store_global_provider_secret",
            new_callable=AsyncMock,
        ) as mock_store_secret,
    ):
        result = await ProviderService.sync_shared_provider_secrets_from_settings(db_session)

    inworld = (
        await db_session.execute(
            select(ProviderKey).where(
                ProviderKey.tenant_id.is_(None),
                ProviderKey.provider_name == "inworld",
                ProviderKey.provider_category == "tts",
            )
        )
    ).scalar_one()

    assert "tts:inworld" in result["synced"]
    assert result["missing"] == []
    assert inworld.secret_ref is not None
    assert inworld.is_default is True
    mock_store_secret.assert_awaited_once_with(inworld.secret_ref, "valid-inworld")