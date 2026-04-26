"""Phone number API tests for tenant workspace filtering."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.phone_numbers.models import PhoneNumber
from tests.conftest import TENANT_1_ID, TENANT_2_ID


@pytest.mark.asyncio
class TestPhoneNumbersApi:
    async def test_list_phone_numbers_for_tenant_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        admin_headers: dict[str, str],
        test_tenant: object,
        test_tenant_2: object,
    ) -> None:
        number_1 = PhoneNumber(
            tenant_id=TENANT_1_ID,
            phone_number="+14155550101",
            country_code="US",
            provider_name="twilio",
            provider_sid="PN111",
            capabilities={"voice": True, "sms": True, "mms": False},
            monthly_cost=Decimal("1.15"),
            status="active",
        )
        number_2 = PhoneNumber(
            tenant_id=TENANT_2_ID,
            phone_number="+14155550102",
            country_code="US",
            provider_name="twilio",
            provider_sid="PN222",
            capabilities={"voice": True, "sms": False, "mms": False},
            monthly_cost=Decimal("1.15"),
            status="active",
        )
        db_session.add_all([number_1, number_2])
        await db_session.flush()

        resp = await client.get(
            f"/api/v1/phone-numbers?tenant_id={TENANT_1_ID}",
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert [item["phone_number"] for item in data["numbers"]] == ["+14155550101"]