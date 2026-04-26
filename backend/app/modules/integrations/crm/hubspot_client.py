"""HubSpot CRM client implementing the BaseCrmClient interface.

Uses HubSpot API v3.  All responses are normalised to Zoho-compatible field
names so that downstream code (CrmDataService, CrmCacheService, campaign
builder) works identically regardless of CRM provider.
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

_BASE = "https://api.hubapi.com"

# ── Field mapping: HubSpot property → Zoho-compatible key ──────────────
_CONTACT_MAP: dict[str, str] = {
    "firstname": "First_Name",
    "lastname": "Last_Name",
    "email": "Email",
    "phone": "Phone",
    "mobilephone": "Mobile",
    "company": "Company",
    "jobtitle": "Title",
    "city": "Mailing_City",
    "state": "Mailing_State",
    "country": "Mailing_Country",
    "hubspot_owner_id": "Owner",
    "createdate": "Created_Time",
    "lastmodifieddate": "Modified_Time",
    "lifecyclestage": "Lifecycle_Stage",
}

_DEAL_MAP: dict[str, str] = {
    "dealname": "Deal_Name",
    "amount": "Amount",
    "dealstage": "Stage",
    "pipeline": "Pipeline",
    "closedate": "Closing_Date",
    "hubspot_owner_id": "Owner",
    "createdate": "Created_Time",
    "lastmodifieddate": "Modified_Time",
}

_COMPANY_MAP: dict[str, str] = {
    "name": "Account_Name",
    "domain": "Website",
    "phone": "Phone",
    "city": "Billing_City",
    "state": "Billing_State",
    "country": "Billing_Country",
    "industry": "Industry",
    "hubspot_owner_id": "Owner",
    "createdate": "Created_Time",
    "lastmodifieddate": "Modified_Time",
}

# Default properties to fetch per object type.
_CONTACT_PROPS = ",".join(_CONTACT_MAP.keys())
_DEAL_PROPS = ",".join(_DEAL_MAP.keys())
_COMPANY_PROPS = ",".join(_COMPANY_MAP.keys())


def _norm(record: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Normalise a HubSpot record dict to Zoho-compatible keys."""
    props: dict[str, Any] = record.get("properties") or {}
    out: dict[str, Any] = {"id": str(record.get("id", ""))}
    for hs_key, zoho_key in mapping.items():
        val = props.get(hs_key)
        if val is not None:
            out[zoho_key] = val
    # Synthesise Full_Name for contacts.
    first = out.get("First_Name", "")
    last = out.get("Last_Name", "")
    if first or last:
        out["Full_Name"] = f"{first} {last}".strip()
    return out


def _reverse_map(mapping: dict[str, str]) -> dict[str, str]:
    """Zoho key → HubSpot property name."""
    return {v: k for k, v in mapping.items()}


class HubSpotCrmClient(BaseCrmClient):
    """Async HubSpot CRM client with automatic token refresh."""

    def __init__(self, db: Any, integration: Any) -> None:
        self._db = db
        self._integration = integration
        self._access_token: str = decrypt(integration.access_token_encrypted)
        self._client: httpx.AsyncClient | None = None
        self._token_expires_at: float = (
            integration.token_expires_at.timestamp() if integration.token_expires_at else 0.0
        )

    # ── Async context manager ──────────────────────────────────────────
    async def __aenter__(self) -> "HubSpotCrmClient":
        self._client = httpx.AsyncClient(
            base_url=_BASE,
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
        logger.info("hubspot.refreshing_token", integration_id=str(self._integration.id))
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.post(
                f"{_BASE}/oauth/v1/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.HUBSPOT_CLIENT_ID,
                    "client_secret": settings.HUBSPOT_CLIENT_SECRET,
                    "refresh_token": decrypt(self._integration.refresh_token_encrypted),
                },
            )
            resp.raise_for_status()
            data = resp.json()

        new_access = data["access_token"]
        expires_in = int(data.get("expires_in", 1800))
        new_refresh = data.get("refresh_token")

        self._access_token = new_access
        self._token_expires_at = time.time() + expires_in

        self._integration.access_token_encrypted = encrypt(new_access)
        self._integration.token_expires_at = datetime.fromtimestamp(
            self._token_expires_at, tz=timezone.utc
        )
        if new_refresh:
            self._integration.refresh_token_encrypted = encrypt(new_refresh)

        self._db.add(self._integration)
        await self._db.flush()

        # Update live client header.
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {new_access}"

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

    # ── Pagination helper ──────────────────────────────────────────────
    async def _list_objects(
        self,
        object_type: str,
        *,
        properties: str,
        mapping: dict[str, str],
        page: int = 1,
        per_page: int = 200,
        sort_by: str | None = None,
        sort_order: str | None = None,
        if_modified_since: str | None = None,
        extra_filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """List HubSpot objects with cursor-based pagination mapped to page numbers.

        We use the **search** endpoint when sorting or filtering is required
        (HubSpot's list endpoint has limited sort/filter support).  Otherwise
        the plain list endpoint is used for speed.
        """
        props_list = [p.strip() for p in properties.split(",") if p.strip()]

        use_search = bool(sort_by or if_modified_since or extra_filters)

        if use_search:
            return await self._search_objects_paged(
                object_type,
                props_list=props_list,
                mapping=mapping,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                sort_order=sort_order,
                if_modified_since=if_modified_since,
                extra_filters=extra_filters or [],
            )

        # Simple list endpoint — skip pages by walking cursors.
        params: dict[str, Any] = {
            "limit": per_page,
            "properties": props_list,
        }

        # Walk forward to the requested page.
        after: str | None = None
        for _ in range(page - 1):
            params_walk = {**params}
            if after:
                params_walk["after"] = after
            data = await self._request("GET", f"/crm/v3/objects/{object_type}", params=params_walk)
            paging = data.get("paging", {}).get("next", {})
            after = paging.get("after")
            if not after:
                return {
                    "data": [],
                    "info": {"more_records": False, "page": page, "per_page": per_page, "count": 0},
                }

        if after:
            params["after"] = after

        data = await self._request("GET", f"/crm/v3/objects/{object_type}", params=params)
        results = data.get("results", [])
        paging = data.get("paging", {}).get("next", {})
        has_more = bool(paging.get("after"))

        records = [_norm(r, mapping) for r in results]
        return {
            "data": records,
            "info": {
                "more_records": has_more,
                "page": page,
                "per_page": per_page,
                "count": len(records),
            },
        }

    async def _search_objects_paged(
        self,
        object_type: str,
        *,
        props_list: list[str],
        mapping: dict[str, str],
        page: int,
        per_page: int,
        sort_by: str | None,
        sort_order: str | None,
        if_modified_since: str | None,
        extra_filters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Use HubSpot search API with pagination via ``after``."""
        filters: list[dict[str, Any]] = list(extra_filters)

        if if_modified_since:
            # HubSpot search expects epoch-ms for datetime filters.
            try:
                dt = datetime.fromisoformat(if_modified_since)
                epoch_ms = int(dt.timestamp() * 1000)
            except (ValueError, TypeError):
                epoch_ms = int(float(if_modified_since) * 1000)
            filters.append(
                {
                    "propertyName": "lastmodifieddate",
                    "operator": "GTE",
                    "value": str(epoch_ms),
                }
            )

        body: dict[str, Any] = {
            "properties": props_list,
            "limit": per_page,
            "filterGroups": [{"filters": filters}] if filters else [],
        }

        # Map sort parameters.
        if sort_by:
            rev = _reverse_map(mapping)
            hs_sort = rev.get(sort_by, sort_by.lower())
            direction = "DESCENDING" if sort_order and sort_order.upper() == "DESC" else "ASCENDING"
            body["sorts"] = [{"propertyName": hs_sort, "direction": direction}]

        # Walk to the requested page.
        after: str | None = None
        for _ in range(page - 1):
            body_walk = {**body}
            if after:
                body_walk["after"] = after
            data = await self._request(
                "POST", f"/crm/v3/objects/{object_type}/search", json_body=body_walk
            )
            paging = data.get("paging", {}).get("next", {})
            after = paging.get("after")
            if not after:
                return {
                    "data": [],
                    "info": {"more_records": False, "page": page, "per_page": per_page, "count": 0},
                }

        if after:
            body["after"] = after

        data = await self._request("POST", f"/crm/v3/objects/{object_type}/search", json_body=body)
        results = data.get("results", [])
        paging = data.get("paging", {}).get("next", {})
        has_more = bool(paging.get("after"))

        records = [_norm(r, mapping) for r in results]
        return {
            "data": records,
            "info": {
                "more_records": has_more,
                "page": page,
                "per_page": per_page,
                "count": len(records),
            },
        }

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
        props = fields if fields else _CONTACT_PROPS
        return await self._list_objects(
            "contacts",
            properties=props,
            mapping=_CONTACT_MAP,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            if_modified_since=if_modified_since,
        )

    async def search_contacts(
        self, *, criteria: str, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        props = [p.strip() for p in _CONTACT_PROPS.split(",") if p.strip()]
        body: dict[str, Any] = {
            "properties": props,
            "limit": per_page,
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "firstname",
                            "operator": "CONTAINS_TOKEN",
                            "value": f"*{criteria}*",
                        },
                    ]
                },
                {
                    "filters": [
                        {
                            "propertyName": "lastname",
                            "operator": "CONTAINS_TOKEN",
                            "value": f"*{criteria}*",
                        },
                    ]
                },
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "CONTAINS_TOKEN",
                            "value": f"*{criteria}*",
                        },
                    ]
                },
            ],
        }
        data = await self._request("POST", "/crm/v3/objects/contacts/search", json_body=body)
        records = [_norm(r, _CONTACT_MAP) for r in data.get("results", [])]
        return {"data": records, "info": {"count": len(records)}}

    async def get_contact(self, contact_id: str) -> dict[str, Any]:
        props = [p.strip() for p in _CONTACT_PROPS.split(",") if p.strip()]
        data = await self._request(
            "GET",
            f"/crm/v3/objects/contacts/{contact_id}",
            params={"properties": props},
        )
        return {"data": [_norm(data, _CONTACT_MAP)]}

    async def upsert_contact(self, data: dict[str, Any]) -> dict[str, Any]:
        rev = _reverse_map(_CONTACT_MAP)
        properties: dict[str, Any] = {}
        for zoho_key, value in data.items():
            hs_key = rev.get(zoho_key)
            if hs_key:
                properties[hs_key] = value

        result = await self._request(
            "POST",
            "/crm/v3/objects/contacts",
            json_body={"properties": properties},
        )
        return {"data": [_norm(result, _CONTACT_MAP)]}

    async def update_contact(self, contact_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing contact by its HubSpot ID."""
        rev = _reverse_map(_CONTACT_MAP)
        properties: dict[str, Any] = {}
        for zoho_key, value in data.items():
            hs_key = rev.get(zoho_key)
            if hs_key:
                properties[hs_key] = value

        result = await self._request(
            "PATCH",
            f"/crm/v3/objects/contacts/{contact_id}",
            json_body={"properties": properties},
        )
        return {"data": [_norm(result, _CONTACT_MAP)]}

    # ── Leads (contacts with lifecyclestage = lead) ────────────────────
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
        props = fields if fields else _CONTACT_PROPS
        lead_filter: list[dict[str, Any]] = [
            {"propertyName": "lifecyclestage", "operator": "EQ", "value": "lead"},
        ]
        return await self._list_objects(
            "contacts",
            properties=props,
            mapping=_CONTACT_MAP,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            if_modified_since=if_modified_since,
            extra_filters=lead_filter,
        )

    async def search_leads(
        self, *, criteria: str, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        props = [p.strip() for p in _CONTACT_PROPS.split(",") if p.strip()]
        body: dict[str, Any] = {
            "properties": props,
            "limit": per_page,
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "lifecyclestage", "operator": "EQ", "value": "lead"},
                        {
                            "propertyName": "firstname",
                            "operator": "CONTAINS_TOKEN",
                            "value": f"*{criteria}*",
                        },
                    ]
                },
                {
                    "filters": [
                        {"propertyName": "lifecyclestage", "operator": "EQ", "value": "lead"},
                        {
                            "propertyName": "lastname",
                            "operator": "CONTAINS_TOKEN",
                            "value": f"*{criteria}*",
                        },
                    ]
                },
                {
                    "filters": [
                        {"propertyName": "lifecyclestage", "operator": "EQ", "value": "lead"},
                        {
                            "propertyName": "email",
                            "operator": "CONTAINS_TOKEN",
                            "value": f"*{criteria}*",
                        },
                    ]
                },
            ],
        }
        data = await self._request("POST", "/crm/v3/objects/contacts/search", json_body=body)
        records = [_norm(r, _CONTACT_MAP) for r in data.get("results", [])]
        return {"data": records, "info": {"count": len(records)}}

    async def upsert_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        data.setdefault("Lifecycle_Stage", "lead")
        return await self.upsert_contact(data)

    # ── Deals ──────────────────────────────────────────────────────────
    async def list_deals(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        props = fields if fields else _DEAL_PROPS
        return await self._list_objects(
            "deals", properties=props, mapping=_DEAL_MAP, page=page, per_page=per_page
        )

    # ── Accounts (Companies in HubSpot) ────────────────────────────────
    async def list_accounts(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        props = fields if fields else _COMPANY_PROPS
        return await self._list_objects(
            "companies", properties=props, mapping=_COMPANY_MAP, page=page, per_page=per_page
        )

    async def search_accounts(
        self, *, criteria: str, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        props = [p.strip() for p in _COMPANY_PROPS.split(",") if p.strip()]
        body: dict[str, Any] = {
            "properties": props,
            "limit": per_page,
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "name",
                            "operator": "CONTAINS_TOKEN",
                            "value": f"*{criteria}*",
                        },
                    ]
                },
            ],
        }
        data = await self._request("POST", "/crm/v3/objects/companies/search", json_body=body)
        records = [_norm(r, _COMPANY_MAP) for r in data.get("results", [])]
        return {"data": records, "info": {"count": len(records)}}

    # ── Activities ─────────────────────────────────────────────────────
    async def list_tasks(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        return await self._list_objects(
            "tasks",
            properties=fields
            or "hs_task_subject,hs_task_body,hs_task_status,hs_task_priority,hubspot_owner_id,createdate,lastmodifieddate",
            mapping={
                "hs_task_subject": "Subject",
                "hs_task_body": "Description",
                "hs_task_status": "Status",
                "hs_task_priority": "Priority",
                "hubspot_owner_id": "Owner",
                "createdate": "Created_Time",
                "lastmodifieddate": "Modified_Time",
            },
            page=page,
            per_page=per_page,
        )

    async def list_calls(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        return await self._list_objects(
            "calls",
            properties=fields
            or "hs_call_title,hs_call_body,hs_call_direction,hs_call_duration,hs_call_status,hubspot_owner_id,createdate",
            mapping={
                "hs_call_title": "Subject",
                "hs_call_body": "Description",
                "hs_call_direction": "Call_Type",
                "hs_call_duration": "Call_Duration",
                "hs_call_status": "Call_Status",
                "hubspot_owner_id": "Owner",
                "createdate": "Created_Time",
            },
            page=page,
            per_page=per_page,
        )

    async def list_notes(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        return await self._list_objects(
            "notes",
            properties=fields or "hs_note_body,hubspot_owner_id,createdate,lastmodifieddate",
            mapping={
                "hs_note_body": "Note_Content",
                "hubspot_owner_id": "Owner",
                "createdate": "Created_Time",
                "lastmodifieddate": "Modified_Time",
            },
            page=page,
            per_page=per_page,
        )

    async def list_meetings(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        return await self._list_objects(
            "meetings",
            properties=fields
            or "hs_meeting_title,hs_meeting_body,hs_meeting_start_time,hs_meeting_end_time,hubspot_owner_id,createdate",
            mapping={
                "hs_meeting_title": "Title",
                "hs_meeting_body": "Description",
                "hs_meeting_start_time": "Start_DateTime",
                "hs_meeting_end_time": "End_DateTime",
                "hubspot_owner_id": "Owner",
                "createdate": "Created_Time",
            },
            page=page,
            per_page=per_page,
        )

    async def list_campaigns(
        self, *, page: int = 1, per_page: int = 200, fields: str = ""
    ) -> dict[str, Any]:
        # HubSpot marketing campaigns are in the Marketing API, not CRM objects.
        # Return empty to avoid breaking the interface.
        return {
            "data": [],
            "info": {"more_records": False, "page": page, "per_page": per_page, "count": 0},
        }

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
        # Map generic params to HubSpot call properties
        direction = (
            "OUTBOUND" if call_type and call_type.lower() in ("outbound", "outgoing") else "INBOUND"
        )
        try:
            duration_ms = str(int(call_duration) * 1000)
        except (ValueError, TypeError):
            duration_ms = "0"

        call_body: dict[str, Any] = {
            "properties": {
                "hs_call_title": subject,
                "hs_call_body": description,
                "hs_call_duration": duration_ms,
                "hs_call_direction": direction,
                "hs_call_status": "COMPLETED",
                "hs_timestamp": call_start_time or datetime.now(timezone.utc).isoformat(),
            },
        }
        # Associate to contact if who_id is provided
        associations: list[dict[str, Any]] = []
        if who_id:
            associations.append(
                {
                    "to": {"id": who_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 194,  # call-to-contact
                        }
                    ],
                }
            )
        # Associate to deal/company if what_id is provided
        if what_id and se_module:
            obj_type = _hs_object_type(se_module)
            type_id = {"deals": 206, "companies": 182}.get(obj_type, 206)
            associations.append(
                {
                    "to": {"id": what_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": type_id,
                        }
                    ],
                }
            )
        if associations:
            call_body["associations"] = associations

        result = await self._request("POST", "/crm/v3/objects/calls", json_body=call_body)
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
            "properties": {
                "hs_note_body": f"**{title}**\n\n{content}" if title else content,
                "hs_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        # Determine association type based on parent_module
        obj_type = _hs_object_type(parent_module)
        assoc_type_map = {"contacts": 202, "companies": 190, "deals": 214}
        assoc_type_id = assoc_type_map.get(obj_type, 202)

        note_body["associations"] = [
            {
                "to": {"id": parent_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": assoc_type_id,
                    }
                ],
            }
        ]
        result = await self._request("POST", "/crm/v3/objects/notes", json_body=note_body)
        return {"data": [{"id": str(result.get("id", ""))}]}

    # ── Phone lookup ───────────────────────────────────────────────────
    async def find_contact_by_phone(self, phone: str) -> dict[str, Any] | None:
        from app.modules.integrations.phone_normalizer import phone_search_variants

        variants = phone_search_variants(phone)
        seen_ids: set[str] = set()

        for variant in variants:
            for prop in ("phone", "mobilephone"):
                body: dict[str, Any] = {
                    "properties": [p.strip() for p in _CONTACT_PROPS.split(",")],
                    "limit": 10,
                    "filterGroups": [
                        {
                            "filters": [
                                {"propertyName": prop, "operator": "EQ", "value": variant},
                            ]
                        },
                    ],
                }
                try:
                    data = await self._request(
                        "POST", "/crm/v3/objects/contacts/search", json_body=body
                    )
                    for r in data.get("results", []):
                        rid = str(r.get("id", ""))
                        if rid and rid not in seen_ids:
                            return _norm(r, _CONTACT_MAP)
                except httpx.HTTPStatusError:
                    continue

        return None

    # ── Module metadata ────────────────────────────────────────────────
    async def describe_module_fields(self, module: str) -> list[dict[str, Any]]:
        obj_type = _hs_object_type(module)
        data = await self._request("GET", f"/crm/v3/properties/{obj_type}")
        fields: list[dict[str, Any]] = []
        for prop in data.get("results", []):
            fields.append(
                {
                    "api_name": prop.get("name", ""),
                    "display_label": prop.get("label", ""),
                    "data_type": prop.get("type", "string"),
                    "read_only": not prop.get("modificationMetadata", {}).get(
                        "readOnlyValue", False
                    )
                    is False,
                    "required": False,  # HubSpot doesn't expose required in list
                }
            )
        return fields

    async def list_module_views(self, module: str) -> list[dict[str, Any]]:
        # HubSpot doesn't have CRM views in the same way as Zoho.
        # Return a default view to satisfy the interface contract.
        return [
            {"id": "all", "name": "All Records", "system_name": "all", "default": True},
        ]

    async def list_records_by_view(
        self,
        module: str,
        cvid: str,
        *,
        page: int = 1,
        per_page: int = 200,
    ) -> dict[str, Any]:
        # HubSpot doesn't have server-side views — fall back to listing all.
        obj_type = _hs_object_type(module)
        mapping = _object_mapping(obj_type)
        props = _default_props(obj_type)
        return await self._list_objects(
            obj_type, properties=props, mapping=mapping, page=page, per_page=per_page
        )

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def get_org_metadata(self) -> dict[str, Any]:
        """Fetch HubSpot portal metadata."""
        try:
            resp = await self._request("GET", f"/oauth/v1/access-tokens/{self._access_token}")
            return {
                "org_id": str(resp.get("hub_id", "")),
                "org_name": resp.get("hub_domain") or resp.get("user"),
            }
        except Exception:
            logger.warning("hubspot_org_metadata_failed")
            return {"org_id": None, "org_name": None}

    async def revoke_token(self) -> None:
        """Best-effort token revocation (HubSpot does not support revocation)."""
        # HubSpot OAuth does not provide a revoke endpoint.
        # Token will naturally expire after its TTL.
        pass


# ── Helpers ────────────────────────────────────────────────────────────


def _hs_object_type(module: str) -> str:
    """Map a Zoho-style module name to a HubSpot object type."""
    mapping: dict[str, str] = {
        "Contacts": "contacts",
        "contacts": "contacts",
        "Leads": "contacts",
        "leads": "contacts",
        "Deals": "deals",
        "deals": "deals",
        "Accounts": "companies",
        "accounts": "companies",
        "Companies": "companies",
        "companies": "companies",
        "Tasks": "tasks",
        "tasks": "tasks",
        "Calls": "calls",
        "calls": "calls",
        "Notes": "notes",
        "notes": "notes",
        "Meetings": "meetings",
        "meetings": "meetings",
    }
    return mapping.get(module, module.lower())


def _object_mapping(obj_type: str) -> dict[str, str]:
    """Get the field mapping dict for a HubSpot object type."""
    if obj_type in ("contacts",):
        return _CONTACT_MAP
    if obj_type in ("deals",):
        return _DEAL_MAP
    if obj_type in ("companies",):
        return _COMPANY_MAP
    return _CONTACT_MAP


def _default_props(obj_type: str) -> str:
    """Get default properties CSV for a HubSpot object type."""
    if obj_type in ("contacts",):
        return _CONTACT_PROPS
    if obj_type in ("deals",):
        return _DEAL_PROPS
    if obj_type in ("companies",):
        return _COMPANY_PROPS
    return _CONTACT_PROPS
