"""Tests for CrmCacheService._crm_record_to_cache_dict and _parse_zoho_datetime."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.integrations.crm_cache_service import InventoryOrchestrator as CrmCacheService, _resolve_temporal_signature as _parse_zoho_datetime

INTEGRATION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


# ── _crm_record_to_cache_dict ───────────────────────────────


def _sample_record(overrides: dict | None = None) -> dict:
    base = {
        "id": "1234567890",
        "Full_Name": "Jane Doe",
        "First_Name": "Jane",
        "Last_Name": "Doe",
        "Email": "jane@example.com",
        "Phone": "+14155551234",
        "Mobile": None,
        "Company": "Acme Inc",
        "Title": "CEO",
        "Lead_Status": None,
        "Lead_Source": "Web",
        "Mailing_City": "Mumbai",
        "Mailing_State": "Maharashtra",
        "Mailing_Country": "India",
        "Owner": {"name": "Admin", "id": "owner123"},
        "Created_Time": "2024-06-15T10:30:00+05:30",
        "Modified_Time": "2024-07-01T14:00:00+05:30",
    }
    if overrides:
        base.update(overrides)
    return base


def test_basic_record_conversion() -> None:
    """Ensure all standard fields map correctly."""
    result = CrmCacheService._crm_record_to_cache_dict(
        _sample_record(),
        integration_id=INTEGRATION_ID,
        tenant_id=TENANT_ID,
        crm_module="Contacts",
    )
    assert result["crm_record_id"] == "1234567890"
    assert result["crm_module"] == "Contacts"
    assert result["tenant_id"] == TENANT_ID
    assert result["integration_id"] == INTEGRATION_ID
    assert result["full_name"] == "Jane Doe"
    assert result["email"] == "jane@example.com"
    assert result["company"] == "Acme Inc"
    assert result["owner_name"] == "Admin"
    assert result["crm_created_time"] is not None
    assert result["crm_modified_time"] is not None


def test_record_with_no_phone() -> None:
    """Null phones should produce None e164 values."""
    result = CrmCacheService._crm_record_to_cache_dict(
        _sample_record({"Phone": None, "Mobile": None}),
        integration_id=INTEGRATION_ID,
        tenant_id=TENANT_ID,
        crm_module="Leads",
    )
    assert result["phone_e164"] is None
    assert result["mobile_e164"] is None
    assert result["phone_raw"] is None
    assert result["crm_module"] == "Leads"


def test_record_with_no_owner() -> None:
    """Owner being None should not crash."""
    result = CrmCacheService._crm_record_to_cache_dict(
        _sample_record({"Owner": None}),
        integration_id=INTEGRATION_ID,
        tenant_id=TENANT_ID,
        crm_module="Contacts",
    )
    assert result["owner_name"] is None


def test_record_preserves_raw_data() -> None:
    """The raw_data field should store the original record dict."""
    record = _sample_record()
    result = CrmCacheService._crm_record_to_cache_dict(
        record,
        integration_id=INTEGRATION_ID,
        tenant_id=TENANT_ID,
        crm_module="Contacts",
    )
    assert result["raw_data"] is record


# ── _parse_zoho_datetime ─────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected_type"),
    [
        ("2024-06-15T10:30:00+05:30", datetime),
        ("2024-01-01T00:00:00+00:00", datetime),
        (None, type(None)),
        ("", type(None)),
    ],
)
def test_parse_zoho_datetime(value: str | None, expected_type: type) -> None:
    result = _parse_zoho_datetime(value)
    assert isinstance(result, expected_type)


def test_parse_zoho_datetime_tz_aware() -> None:
    result = _parse_zoho_datetime("2024-06-15T10:30:00+05:30")
    assert result is not None
    assert result.tzinfo is not None
