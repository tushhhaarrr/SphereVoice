"""Salesforce CRM client implementing the BaseCrmClient interface.

Uses Salesforce REST API v59.0. All responses are normalised to Zoho-compatible
field names so that downstream code works identically regardless of CRM provider.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.modules.integrations.crm.base_client import BaseCrmClient

logger = structlog.get_logger(__name__)
settings = get_settings()

_API_VERSION = "v59.0"

# ── Field mapping: Salesforce field → Zoho-compatible key ──────────────
_CONTACT_MAP: dict[str, str] = {
    "FirstName": "First_Name",
    "LastName": "Last_Name",
    "Email": "Email",
    "Phone": "Phone",
    "MobilePhone": "Mobile",
    "Title": "Title",
    "MailingCity": "Mailing_City",
    "MailingState": "Mailing_State",
    "MailingCountry": "Mailing_Country",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
    "LastModifiedDate": "Modified_Time",
}

_LEAD_MAP: dict[str, str] = {
    "FirstName": "First_Name",
    "LastName": "Last_Name",
    "Email": "Email",
    "Phone": "Phone",
    "MobilePhone": "Mobile",
    "Company": "Company",
    "Title": "Title",
    "City": "Mailing_City",
    "State": "Mailing_State",
    "Country": "Mailing_Country",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
    "LastModifiedDate": "Modified_Time",
}

_DEAL_MAP: dict[str, str] = {  # Opportunity in Salesforce
    "Name": "Deal_Name",
    "Amount": "Amount",
    "StageName": "Stage",
    "Type": "Pipeline",
    "CloseDate": "Closing_Date",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
    "LastModifiedDate": "Modified_Time",
}

_ACCOUNT_MAP: dict[str, str] = {
    "Name": "Account_Name",
    "Website": "Website",
    "Phone": "Phone",
    "BillingCity": "Billing_City",
    "BillingState": "Billing_State",
    "BillingCountry": "Billing_Country",
    "Industry": "Industry",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
    "LastModifiedDate": "Modified_Time",
}

_TASK_MAP: dict[str, str] = {
    "Subject": "Subject",
    "Description": "Description",
    "Status": "Status",
    "Priority": "Priority",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
    "LastModifiedDate": "Modified_Time",
}

_CALL_MAP: dict[str, str] = {
    "Subject": "Subject",
    "Description": "Description",
    "CallType": "Call_Type",
    "CallDurationInSeconds": "Call_Duration",
    "ActivityDate": "Call_Date",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
}

_NOTE_MAP: dict[str, str] = {
    "Title": "Note_Title",
    "Body": "Note_Content",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
    "LastModifiedDate": "Modified_Time",
}

_MEETING_MAP: dict[str, str] = {
    "Subject": "Title",
    "Description": "Description",
    "StartDateTime": "Start_DateTime",
    "EndDateTime": "End_DateTime",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
}

_CAMPAIGN_MAP: dict[str, str] = {
    "Name": "Campaign_Name",
    "Type": "Type",
    "Status": "Status",
    "StartDate": "Start_Date",
    "EndDate": "End_Date",
    "OwnerId": "Owner",
    "CreatedDate": "Created_Time",
}


def _norm(record: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Normalise a Salesforce record dict to Zoho-compatible keys."""
    out: dict[str, Any] = {"id": str(record.get("Id", record.get("id", "")))}
    for sf_key, zoho_key in mapping.items():
        val = record.get(sf_key)
        if val is not None:
            out[zoho_key] = val
    # Synthesise Full_Name for contacts/leads.
    first = out.get("First_Name", "")
    last = out.get("Last_Name", "")
    if first or last:
        out["Full_Name"] = f"{first} {last}".strip()
    return out


def _reverse_map(mapping: dict[str, str]) -> dict[str, str]:
    """Zoho key → Salesforce field name."""
    return {v: k for k, v in mapping.items()}


def _sf_object_type(module: str) -> str:
    """Map generic module name to Salesforce SObject type."""
    mapping: dict[str, str] = {
        "Contacts": "Contact",
        "contacts": "Contact",
        "Leads": "Lead",
        "leads": "Lead",
        "Deals": "Opportunity",
        "deals": "Opportunity",
        "Accounts": "Account",
        "accounts": "Account",
        "Companies": "Account",
        "companies": "Account",
        "Tasks": "Task",
        "tasks": "Task",
        "Calls": "Task",
        "calls": "Task",
        "Notes": "Note",
        "notes": "Note",
        "Meetings": "Event",
        "meetings": "Event",
        "Campaigns": "Campaign",
        "campaigns": "Campaign",
    }
    return mapping.get(module, module)


def _object_mapping(sf_type: str) -> dict[str, str]:
    """Get the field mapping dict for a Salesforce object type."""
    if sf_type == "Contact":
        return _CONTACT_MAP
    if sf_type == "Lead":
        return _LEAD_MAP
    if sf_type == "Opportunity":
        return _DEAL_MAP
    if sf_type == "Account":
        return _ACCOUNT_MAP
    if sf_type == "Task":
        return _TASK_MAP
    if sf_type == "Event":
        return _MEETING_MAP
    if sf_type == "Note":
        return _NOTE_MAP
    if sf_type == "Campaign":
        return _CAMPAIGN_MAP
    return _CONTACT_MAP


def _contact_fields() -> str:
    """Get SOQL field list for Contact object."""
    return "Id," + ",".join(_CONTACT_MAP.keys())


def _lead_fields() -> str:
    """Get SOQL field list for Lead object."""
    return "Id," + ",".join(_LEAD_MAP.keys())


def _deal_fields() -> str:
    """Get SOQL field list for Opportunity object."""
    return "Id," + ",".join(_DEAL_MAP.keys())


def _account_fields() -> str:
    """Get SOQL field list for Account object."""
    return "Id," + ",".join(_ACCOUNT_MAP.keys())


def _task_fields() -> str:
    """Get SOQL field list for Task object."""
    return "Id," + ",".join(_TASK_MAP.keys())


def _call_fields() -> str:
    """Get SOQL field list for Call (Task with TaskSubtype='Call') object."""
    return "Id," + ",".join(_CALL_MAP.keys())


def _note_fields() -> str:
    """Get SOQL field list for Note object."""
    return "Id," + ",".join(_NOTE_MAP.keys())


def _meeting_fields() -> str:
    """Get SOQL field list for Event object."""
    return "Id," + ",".join(_MEETING_MAP.keys())


def _campaign_fields() -> str:
    """Get SOQL field list for Campaign object."""
    return "Id," + ",".join(_CAMPAIGN_MAP.keys())


class SalesforceCrmClient(BaseCrmClient):
    """Async Salesforce CRM client with automatic token refresh."""

    def __init__(self, db: Any, integration: Any) -> None:
        self._db = db
        self._integration = integration
        self._access_token: str = decrypt(integration.access_token_encrypted)
        # Salesforce stores instance_url in the data_center field
        self._instance_url: str = integration.data_center or "https://login.salesforce.com"
        self._client: httpx.AsyncClient | None = None
        self._token_expires_at: float = (
            integration.token_expires_at.timestamp() if integration.token_expires_at else 0.0
        )

    # ── Async context manager ──────────────────────────────────────────
    async def __aenter__(self) -> "SalesforceCrmClient":
        self._client = httpx.AsyncClient(
            base_url=self._instance_url,
            timeout=30.0,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Token management ───────────────────────────────────────────────
    async def _ensure_valid_token(self) -> None:
        if time.time() < self._token_expires_at - 120:
            return
        await self._refresh_token()

    async def _refresh_token(self) -> None:
        logger.info("salesforce.refreshing_token", integration_id=str(self._integration.id))
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.post(
                "https://login.salesforce.com/services/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.SALESFORCE_CLIENT_ID,
                    "client_secret": settings.SALESFORCE_CLIENT_SECRET,
                    "refresh_token": decrypt(self._integration.refresh_token_encrypted),
                },
            )
            resp.raise_for_status()
            data = resp.json()

        new_access = data["access_token"]
        # Salesforce does NOT return expires_in by default; use 2 hours as safe default
        expires_in = int(data.get("expires_in", 7200))
        # Salesforce does NOT return a new refresh_token on refresh
        # Also update instance_url if provided in the response
        new_instance_url = data.get("instance_url")

        self._access_token = new_access
        self._token_expires_at = time.time() + expires_in
        if new_instance_url:
            self._instance_url = new_instance_url
            self._integration.data_center = new_instance_url

        self._integration.access_token_encrypted = encrypt(new_access)
        self._integration.token_expires_at = datetime.fromtimestamp(
            self._token_expires_at, tz=timezone.utc
        )

        self._db.add(self._integration)
        await self._db.flush()

        # Update live client
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {new_access}"
            if new_instance_url:
                # Recreate client with new base URL
                await self._client.aclose()
                self._client = httpx.AsyncClient(
                    base_url=self._instance_url,
                    timeout=30.0,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )

    # ── Core HTTP helper ───────────────────────────────────────────────
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self._client is not None, "Client not initialised — use async with."
        await self._ensure_valid_token()

        resp = await self._client.request(method, path, params=params, json=json_body)

        # Retry once on 401 (token may have been rotated externally).
        if resp.status_code == 401:
            await self._refresh_token()
            resp = await self._client.request(method, path, params=params, json=json_body)

        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()  # type: ignore[no-any-return]

    # ── SOQL Query helper ──────────────────────────────────────────────
    async def _query_soql(
        self,
        soql: str,
        *,
        mapping: dict[str, str],
        page: int = 1,
        per_page: int = 200,
    ) -> dict[str, Any]:
        """Execute a SOQL query with pagination.

        Uses OFFSET/LIMIT for pagination. Salesforce allows OFFSET up to 2000.
        For larger datasets, would need to use queryMore with nextRecordsUrl.
        """
        offset = (page - 1) * per_page
        paginated_soql = f"{soql} LIMIT {per_page} OFFSET {offset}"

        data = await self._request(
            "GET",
            f"/services/data/{_API_VERSION}/query/",
            params={"q": paginated_soql},
        )

        records = data.get("records", [])
        total_size = data.get("totalSize", 0)
        done = data.get("done", True)

        # Calculate if there are more records
        has_more = not done or (offset + len(records) < total_size)

        normalized = [_norm(r, mapping) for r in records]
        return {
            "data": normalized,
            "info": {
                "more_records": has_more,
                "page": page,
                "per_page": per_page,
                "count": len(normalized),
            },
        }

    async def _query_soql_all(
        self,
        soql: str,
        *,
        mapping: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Execute a SOQL query and return all results (for small result sets)."""
        data = await self._request(
            "GET",
            f"/services/data/{_API_VERSION}/query/",
            params={"q": soql},
        )
        records = data.get("records", [])
        return [_norm(r, mapping) for r in records]

    # ── Contacts ───────────────────────────────────────────────────────
    async def list_contacts(
        self,
        *,
        page: int = 1,
        per_page: int = 200,
        fields: str = "",
        sort_by: str | None = None,
        sort_order: str | None = None,
        if_modified_since: str | None = None,
    ) -> dict[str, Any]:
        select_fields = fields if fields else _contact_fields()
        soql = f"SELECT {select_fields} FROM Contact"

        if if_modified_since:
            # Convert ISO timestamp to Salesforce datetime format
            soql += f" WHERE LastModifiedDate > {if_modified_since}"

        # Handle sorting
        if sort_by:
            rev = _reverse_map(_CONTACT_MAP)
            sf_sort = rev.get(sort_by, sort_by)
            order = "DESC" if sort_order and sort_order.upper() == "DESC" else "ASC"
            soql += f" ORDER BY {sf_sort} {order}"
        else:
            soql += " ORDER BY LastModifiedDate DESC"

        return await self._query_soql(soql, mapping=_CONTACT_MAP, page=page, per_page=per_page)

    async def search_contacts(
        self, *, criteria: str, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        escaped = criteria.replace("'", "\\'")
        soql = (
            f"SELECT {_contact_fields()} FROM Contact "
            f"WHERE Name LIKE '%{escaped}%' OR Email LIKE '%{escaped}%'"
        )
        return await self._query_soql(soql, mapping=_CONTACT_MAP, page=page, per_page=per_page)

    async def get_contact(self, contact_id: str) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"/services/data/{_API_VERSION}/sobjects/Contact/{contact_id}",
        )
        return {"data": [_norm(data, _CONTACT_MAP)]}

    async def upsert_contact(self, data: dict[str, Any]) -> dict[str, Any]:
        rev = _reverse_map(_CONTACT_MAP)
        properties: dict[str, Any] = {}
        record_id = data.get("id")

        for zoho_key, value in data.items():
            if zoho_key == "id":
                continue
            sf_key = rev.get(zoho_key)
            if sf_key:
                properties[sf_key] = value

        if record_id:
            # Update existing record
            await self._request(
                "PATCH",
                f"/services/data/{_API_VERSION}/sobjects/Contact/{record_id}",
                json_body=properties,
            )
            return {"data": [{"id": record_id}]}
        else:
            # Create new record
            result = await self._request(
                "POST",
                f"/services/data/{_API_VERSION}/sobjects/Contact/",
                json_body=properties,
            )
            return {"data": [{"id": str(result.get("id", ""))}]}

    # ── Leads ──────────────────────────────────────────────────────────
    async def list_leads(
        self,
        *,
        page: int = 1,
        per_page: int = 200,
        fields: str = "",
        sort_by: str | None = None,
        sort_order: str | None = None,
        if_modified_since: str | None = None,
    ) -> dict[str, Any]:
        select_fields = fields if fields else _lead_fields()
        soql = f"SELECT {select_fields} FROM Lead"

        if if_modified_since:
            soql += f" WHERE LastModifiedDate > {if_modified_since}"

        if sort_by:
            rev = _reverse_map(_LEAD_MAP)
            sf_sort = rev.get(sort_by, sort_by)
            order = "DESC" if sort_order and sort_order.upper() == "DESC" else "ASC"
            soql += f" ORDER BY {sf_sort} {order}"
        else:
            soql += " ORDER BY LastModifiedDate DESC"

        return await self._query_soql(soql, mapping=_LEAD_MAP, page=page, per_page=per_page)

    async def search_leads(
        self, *, criteria: str, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        escaped = criteria.replace("'", "\\'")
        soql = (
            f"SELECT {_lead_fields()} FROM Lead "
            f"WHERE Name LIKE '%{escaped}%' OR Email LIKE '%{escaped}%'"
        )
        return await self._query_soql(soql, mapping=_LEAD_MAP, page=page, per_page=per_page)

    async def upsert_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        rev = _reverse_map(_LEAD_MAP)
        properties: dict[str, Any] = {}
        record_id = data.get("id")

        for zoho_key, value in data.items():
            if zoho_key == "id":
                continue
            sf_key = rev.get(zoho_key)
            if sf_key:
                properties[sf_key] = value

        if record_id:
            await self._request(
                "PATCH",
                f"/services/data/{_API_VERSION}/sobjects/Lead/{record_id}",
                json_body=properties,
            )
            return {"data": [{"id": record_id}]}
        else:
            result = await self._request(
                "POST",
                f"/services/data/{_API_VERSION}/sobjects/Lead/",
                json_body=properties,
            )
            return {"data": [{"id": str(result.get("id", ""))}]}

    # ── Deals (Opportunities) ──────────────────────────────────────────
    async def list_deals(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        select_fields = fields if fields else _deal_fields()
        soql = f"SELECT {select_fields} FROM Opportunity ORDER BY LastModifiedDate DESC"
        return await self._query_soql(soql, mapping=_DEAL_MAP, page=page, per_page=per_page)

    # ── Accounts ───────────────────────────────────────────────────────
    async def list_accounts(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        select_fields = fields if fields else _account_fields()
        soql = f"SELECT {select_fields} FROM Account ORDER BY LastModifiedDate DESC"
        return await self._query_soql(soql, mapping=_ACCOUNT_MAP, page=page, per_page=per_page)

    async def search_accounts(
        self, *, criteria: str, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        escaped = criteria.replace("'", "\\'")
        soql = f"SELECT {_account_fields()} FROM Account WHERE Name LIKE '%{escaped}%'"
        return await self._query_soql(soql, mapping=_ACCOUNT_MAP, page=page, per_page=per_page)

    # ── Activities ─────────────────────────────────────────────────────
    async def list_tasks(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        select_fields = fields if fields else _task_fields()
        soql = f"SELECT {select_fields} FROM Task ORDER BY LastModifiedDate DESC"
        return await self._query_soql(soql, mapping=_TASK_MAP, page=page, per_page=per_page)

    async def list_calls(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        select_fields = fields if fields else _call_fields()
        soql = (
            f"SELECT {select_fields} FROM Task WHERE TaskSubtype = 'Call' ORDER BY CreatedDate DESC"
        )
        return await self._query_soql(soql, mapping=_CALL_MAP, page=page, per_page=per_page)

    async def list_notes(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        select_fields = fields if fields else _note_fields()
        soql = f"SELECT {select_fields} FROM Note ORDER BY LastModifiedDate DESC"
        return await self._query_soql(soql, mapping=_NOTE_MAP, page=page, per_page=per_page)

    async def list_meetings(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        select_fields = fields if fields else _meeting_fields()
        soql = f"SELECT {select_fields} FROM Event ORDER BY CreatedDate DESC"
        return await self._query_soql(soql, mapping=_MEETING_MAP, page=page, per_page=per_page)

    async def list_campaigns(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        select_fields = fields if fields else _campaign_fields()
        soql = f"SELECT {select_fields} FROM Campaign ORDER BY CreatedDate DESC"
        return await self._query_soql(soql, mapping=_CAMPAIGN_MAP, page=page, per_page=per_page)

    # ── Call logging ───────────────────────────────────────────────────
    async def log_call(
        self,
        *,
        subject: str,
        call_type: str,
        call_start_time: str,
        call_duration: str,
        description: str = "",
        who_id: str | None = None,
        what_id: str | None = None,
        se_module: str | None = None,
        call_purpose: str = "None",
        call_result: str | None = None,
    ) -> dict[str, Any]:
        # Determine call direction
        direction = (
            "Outbound" if call_type and call_type.lower() in ("outbound", "outgoing") else "Inbound"
        )

        # Parse call duration to seconds
        try:
            duration_seconds = int(call_duration)
        except (ValueError, TypeError):
            duration_seconds = 0

        # Get activity date from call_start_time (YYYY-MM-DD format)
        activity_date = (
            call_start_time[:10]
            if call_start_time and len(call_start_time) >= 10
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )

        task_body: dict[str, Any] = {
            "Subject": subject,
            "Description": description,
            "TaskSubtype": "Call",
            "CallType": direction,
            "CallDurationInSeconds": duration_seconds,
            "ActivityDate": activity_date,
            "Status": "Completed",
        }

        # Associate to contact/lead if who_id is provided
        if who_id:
            task_body["WhoId"] = who_id

        # Associate to account/opportunity if what_id is provided
        if what_id:
            task_body["WhatId"] = what_id

        result = await self._request(
            "POST",
            f"/services/data/{_API_VERSION}/sobjects/Task/",
            json_body=task_body,
        )
        return {"data": [{"id": str(result.get("id", ""))}]}

    # ── Notes ──────────────────────────────────────────────────────────
    async def add_note(
        self,
        *,
        parent_module: str,
        parent_id: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        note_body: dict[str, Any] = {
            "Title": title,
            "Body": content,
            "ParentId": parent_id,
        }

        result = await self._request(
            "POST",
            f"/services/data/{_API_VERSION}/sobjects/Note/",
            json_body=note_body,
        )
        return {"data": [{"id": str(result.get("id", ""))}]}

    # ── Phone lookup ───────────────────────────────────────────────────
    async def find_contact_by_phone(self, phone: str) -> dict[str, Any] | None:
        from app.modules.integrations.phone_normalizer import phone_search_variants

        variants = phone_search_variants(phone)

        # Try Contacts first
        for variant in variants:
            escaped = variant.replace("'", "\\'")
            soql = (
                f"SELECT {_contact_fields()} FROM Contact "
                f"WHERE Phone = '{escaped}' OR MobilePhone = '{escaped}' LIMIT 1"
            )
            try:
                data = await self._request(
                    "GET",
                    f"/services/data/{_API_VERSION}/query/",
                    params={"q": soql},
                )
                records = data.get("records", [])
                if records:
                    result = _norm(records[0], _CONTACT_MAP)
                    result["_SphereVoice_module"] = "Contacts"
                    return result
            except httpx.HTTPStatusError:
                continue

        # Then try Leads
        for variant in variants:
            escaped = variant.replace("'", "\\'")
            soql = (
                f"SELECT {_lead_fields()} FROM Lead "
                f"WHERE Phone = '{escaped}' OR MobilePhone = '{escaped}' LIMIT 1"
            )
            try:
                data = await self._request(
                    "GET",
                    f"/services/data/{_API_VERSION}/query/",
                    params={"q": soql},
                )
                records = data.get("records", [])
                if records:
                    result = _norm(records[0], _LEAD_MAP)
                    result["_SphereVoice_module"] = "Leads"
                    return result
            except httpx.HTTPStatusError:
                continue

        return None

    # ── Module metadata ────────────────────────────────────────────────
    async def describe_module_fields(self, module: str) -> list[dict[str, Any]]:
        sf_object = _sf_object_type(module)
        data = await self._request(
            "GET",
            f"/services/data/{_API_VERSION}/sobjects/{sf_object}/describe/",
        )
        fields: list[dict[str, Any]] = []
        for f in data.get("fields", []):
            fields.append(
                {
                    "api_name": f.get("name", ""),
                    "display_label": f.get("label", ""),
                    "data_type": f.get("type", "string"),
                    "read_only": not f.get("updateable", True),
                    "required": (
                        not f.get("nillable", True) and not f.get("defaultedOnCreate", False)
                    ),
                }
            )
        return fields

    async def list_module_views(self, module: str) -> list[dict[str, Any]]:
        sf_object = _sf_object_type(module)
        try:
            data = await self._request(
                "GET",
                f"/services/data/{_API_VERSION}/sobjects/{sf_object}/listviews/",
            )
            views: list[dict[str, Any]] = []
            for v in data.get("listviews", []):
                views.append(
                    {
                        "id": v.get("id", ""),
                        "name": v.get("label", ""),
                        "system_name": v.get("developerName", ""),
                        "default": False,
                    }
                )
            return views
        except httpx.HTTPStatusError:
            # Fallback if listviews not available
            logger.warning(
                "salesforce_list_views_failed",
                module=module,
                sf_object=sf_object,
            )
            return [
                {
                    "id": "all",
                    "name": "All Records",
                    "system_name": "all",
                    "default": True,
                }
            ]

    async def list_records_by_view(
        self,
        module: str,
        cvid: str,
        *,
        page: int = 1,
        per_page: int = 200,
    ) -> dict[str, Any]:
        sf_object = _sf_object_type(module)
        mapping = _object_mapping(sf_object)

        # If view ID is "all", just list all records
        if cvid == "all":
            fields_func = {
                "Contact": _contact_fields,
                "Lead": _lead_fields,
                "Opportunity": _deal_fields,
                "Account": _account_fields,
                "Task": _task_fields,
                "Event": _meeting_fields,
                "Note": _note_fields,
                "Campaign": _campaign_fields,
            }.get(sf_object, _contact_fields)

            soql = f"SELECT {fields_func()} FROM {sf_object} ORDER BY LastModifiedDate DESC"
            return await self._query_soql(soql, mapping=mapping, page=page, per_page=per_page)

        # Use listview results endpoint
        try:
            data = await self._request(
                "GET",
                f"/services/data/{_API_VERSION}/sobjects/{sf_object}/listviews/{cvid}/results",
            )
            records = data.get("records", [])
            # ListView results have a different structure
            normalized = []
            for r in records:
                # ListView results store values in 'columns' array
                record_dict: dict[str, Any] = {}
                columns = r.get("columns", [])
                for col in columns:
                    field_name = col.get("fieldNameOrPath", "")
                    value = col.get("value")
                    if field_name and value is not None:
                        record_dict[field_name] = value
                if record_dict:
                    normalized.append(_norm(record_dict, mapping))

            return {
                "data": normalized,
                "info": {
                    "more_records": len(normalized) >= per_page,
                    "page": page,
                    "per_page": per_page,
                    "count": len(normalized),
                },
            }
        except httpx.HTTPStatusError as e:
            logger.warning(
                "salesforce_list_view_failed",
                module=module,
                cvid=cvid,
                error=str(e),
            )
            # Fallback to listing all records
            return await self.list_records_by_view(module, "all", page=page, per_page=per_page)

    # ── Lifecycle ──────────────────────────────────────────────────────
    async def get_org_metadata(self) -> dict[str, Any]:
        """Fetch Salesforce organization metadata."""
        try:
            data = await self._request(
                "GET",
                f"/services/data/{_API_VERSION}/query/",
                params={"q": "SELECT Id, Name FROM Organization LIMIT 1"},
            )
            records = data.get("records", [])
            if records:
                return {
                    "org_id": records[0].get("Id"),
                    "org_name": records[0].get("Name"),
                }
        except Exception:
            logger.warning("salesforce_org_metadata_failed")
        return {"org_id": None, "org_name": None}

    async def revoke_token(self) -> None:
        """Best-effort token revocation."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                await c.post(
                    "https://login.salesforce.com/services/oauth2/revoke",
                    data={"token": self._access_token},
                )
        except Exception:
            logger.warning("salesforce_revoke_failed")
