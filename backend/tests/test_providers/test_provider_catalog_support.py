"""Focused tests for provider catalog support additions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.providers.models import ProviderKey
from app.modules.providers.service import VectorRegistry


@pytest.mark.asyncio
async def test_refresh_provider_catalog_populates_sarvam_static_catalog(db_session) -> None:
    provider = ProviderKey(
        vector_id="sarvam",
        vector_category="tts",
        tenant_id=None,
        auth_sig_encrypted="unused",
        config={},
    )
    db_session.add(provider)
    await db_session.flush()

    with patch(
        "app.modules.providers.service._resolve_auth_signature",
        new=AsyncMock(return_value="sarvam-key"),
    ):
        refreshed = await VectorRegistry.sync_vector_catalog(db_session, provider.id)

    catalog = refreshed.config["catalog"]
    assert refreshed.config["model"] == "bulbul:v3"
    assert refreshed.config["voice_id"] == "aditya"
    assert catalog["source"] == "docs"
    assert any(voice["id"] == "anushka" for voice in catalog["voices"])
    assert any(voice["id"] == "aditya" for voice in catalog["voices"])


@pytest.mark.asyncio
async def test_refresh_provider_catalog_populates_smallest_voice_catalog(db_session) -> None:
    provider = ProviderKey(
        vector_id="smallest",
        vector_category="tts",
        tenant_id=None,
        auth_sig_encrypted="unused",
        config={"model": "lightning-v3.1"},
    )
    db_session.add(provider)
    await db_session.flush()

    with (
        patch(
            "app.modules.providers.service._resolve_auth_signature",
            new=AsyncMock(return_value="smallest-key"),
        ),
        patch(
            "app.modules.providers.service._smallest_request_json",
            new=AsyncMock(
                return_value={
                    "voices": [
                        {"voice_id": "magnus", "language": "en", "gender": "male"},
                        {"voice_id": "olivia", "language": "en", "gender": "female"},
                    ]
                }
            ),
        ),
    ):
        refreshed = await VectorRegistry.sync_vector_catalog(db_session, provider.id)

    catalog = refreshed.config["catalog"]
    assert refreshed.config["model"] == "lightning-v3.1"
    assert refreshed.config["voice_id"] == "magnus"
    assert catalog["source"] == "api"
    assert any(voice["id"] == "magnus" for voice in catalog["voices"])
    assert any(model["id"] == "lightning-v3.1" for model in catalog["models"])