"""Tests for CRM OAuth helpers (state generation/verification, dispatchers)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.core.exceptions import ValidationError
from app.modules.integrations.service import (
    IntegrationService,
    _generate_oauth_state,
    _infer_data_center,
    _verify_oauth_state,
)


# ── OAuth state round-trip ─────────────────────────────────

TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER = uuid.UUID("11111111-1111-1111-1111-111111111111")


def test_state_generate_verify_roundtrip() -> None:
    state = _generate_oauth_state(TENANT, USER, "eu")
    tid, uid, dc = _verify_oauth_state(state)
    assert tid == TENANT
    assert uid == USER
    assert dc == "eu"


def test_state_default_data_center() -> None:
    state = _generate_oauth_state(TENANT, USER)
    _, _, dc = _verify_oauth_state(state)
    assert dc == "in"


def test_state_rejects_tampered_signature() -> None:
    state = _generate_oauth_state(TENANT, USER, "com")
    # flip last char of signature
    tampered = state[:-1] + ("a" if state[-1] != "a" else "b")
    with pytest.raises(ValidationError, match="signature"):
        _verify_oauth_state(tampered)


def test_state_rejects_missing_separator() -> None:
    with pytest.raises(ValidationError, match="missing"):
        _verify_oauth_state("no-dot-separator")


def test_state_rejects_empty_string() -> None:
    with pytest.raises(ValidationError, match="missing"):
        _verify_oauth_state("")


# ── _infer_data_center ───────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://accounts.zoho.eu", "eu"),
        ("https://accounts.zoho.in", "in"),
        ("https://accounts.zoho.com.au", "au"),
        ("https://accounts.zoho.jp", "jp"),
        ("https://accounts.zohocloud.ca", "ca"),
        ("https://accounts.zoho.uk", "uk"),
        ("https://accounts.zoho.com", "com"),
        (None, "com"),
    ],
)
def test_infer_data_center(url: str | None, expected: str) -> None:
    assert _infer_data_center(url) == expected


# ── Generic dispatchers ─────────────────────────────────────


def test_build_oauth_url_unsupported_provider() -> None:
    with pytest.raises(ValidationError, match="Unsupported CRM provider"):
        IntegrationService.build_oauth_url("pipedrive", TENANT, USER)


@pytest.mark.asyncio
async def test_handle_oauth_callback_unsupported_provider() -> None:
    with pytest.raises(ValidationError, match="Unsupported CRM provider"):
        await IntegrationService.handle_oauth_callback(
            "pipedrive",
            db=None,  # type: ignore[arg-type]
            code="x",
            state="y",
        )


def test_build_oauth_url_zoho_dispatches() -> None:
    """Verify zoho_crm dispatches to build_zoho_auth_url."""
    with patch.object(IntegrationService, "build_zoho_auth_url", return_value="https://zoho.example") as mock:
        url = IntegrationService.build_oauth_url("zoho_crm", TENANT, USER, data_center="eu")
        mock.assert_called_once_with(TENANT, USER, "eu")
        assert url == "https://zoho.example"
