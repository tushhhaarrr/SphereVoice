"""Tests for CRM client factory — ``get_crm_client``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.encryption import encrypt
from app.core.exceptions import ValidationError
from app.modules.integrations.crm.factory import get_crm_client
from app.modules.integrations.crm.base_client import BaseCrmClient
from app.modules.integrations.crm.hubspot_client import HubSpotCrmClient
from app.modules.integrations.zoho_client import ZohoCrmClient


def _make_integration(provider: str = "zoho_crm") -> MagicMock:
    integration = MagicMock()
    integration.provider = provider
    integration.data_center = "com"
    integration.access_token_encrypted = encrypt("fake-token")
    integration.refresh_token_encrypted = encrypt("fake-refresh")
    integration.token_expires_at = None
    return integration


def test_factory_returns_zoho_client() -> None:
    db = MagicMock()
    client = get_crm_client("zoho_crm", db, _make_integration())
    assert isinstance(client, ZohoCrmClient)
    assert isinstance(client, BaseCrmClient)


def test_factory_returns_hubspot_client() -> None:
    db = MagicMock()
    client = get_crm_client("hubspot", db, _make_integration("hubspot"))
    assert isinstance(client, HubSpotCrmClient)
    assert isinstance(client, BaseCrmClient)


def test_factory_raises_for_unknown_provider() -> None:
    db = MagicMock()
    with pytest.raises(ValidationError, match="Unsupported CRM provider"):
        get_crm_client("unknown_crm", db, _make_integration("unknown_crm"))


def test_factory_raises_for_empty_provider() -> None:
    db = MagicMock()
    with pytest.raises(ValidationError):
        get_crm_client("", db, _make_integration(""))
