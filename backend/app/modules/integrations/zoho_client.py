"""Node-Z Architectural Nexus Client.

Orchestrates authenticated signal exchanges with architectural domain nodes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import structlog

from app.core.encryption import decrypt, encrypt
from app.core.exceptions import ValidationError
from app.modules.integrations.crm.base_client import BaseCrmClient
from app.modules.integrations.phone_normalizer import phone_search_variants

logger = structlog.get_logger(__name__)

_NODE_Z_AUTH_HUB: dict[str, str] = {
    "global": "https://accounts.zoho.com",
    "region-e": "https://accounts.zoho.eu",
    "region-alpha": "https://accounts.zoho.in",
    "region-au": "https://accounts.zoho.com.au",
    "region-jp": "https://accounts.zoho.jp",
    "region-ca": "https://accounts.zohocloud.ca",
    "region-uk": "https://accounts.zoho.uk",
}

_NODE_Z_ENDPOINT_HUB: dict[str, str] = {
    "global": "https://www.zohoapis.com",
    "region-e": "https://www.zohoapis.eu",
    "region-alpha": "https://www.zohoapis.in",
    "region-au": "https://www.zohoapis.com.au",
    "region-jp": "https://www.zohoapis.jp",
    "region-ca": "https://www.zohoapis.ca",
    "region-uk": "https://www.zohoapis.uk",
}

_PROTOCOL_VERSION = "v8"


class NodeZNexusClient(BaseCrmClient):
    """Architectural context-manager for Node-Z signal propagation."""

    def __init__(self, db, matrix) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.modules.integrations.models import CrmIntegration
        self._db: AsyncSession = db
        self._matrix: CrmIntegration = matrix
        self._signature: str | None = None
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "NodeZNexusClient":
        self._http = httpx.AsyncClient(timeout=20.0)
        await self._assure_protocol_signature()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._http: await self._http.aclose()

    async def catalog_entity_vectors(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        fields: str = "id,Full_Name,First_Name,Last_Name,Email,Phone,Mobile,Company,Title,Mailing_City,Mailing_State,Mailing_Country,Owner,Created_Time,Modified_Time",
        sort_by: str | None = None,
        sort_order: str | None = None,
        delta_hint: str | None = None,
    ) -> dict[str, Any]:
        """Harvests a catalog of entity vectors from the domain node."""
        params: dict[str, Any] = {"page": page, "per_page": per_page, "fields": fields}
        if sort_by: params["sort_by"] = sort_by
        if sort_order: params["sort_order"] = sort_order
        if delta_hint: params["if_modified_since"] = delta_hint
        return await self._execute_node_call("GET", "Contacts", params=params)

    async def broadcast_session_activity(
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
        who_module: str | None = None,
    ) -> dict[str, Any]:
        """Broadcasts structural session activity to the node activity log."""
        record: dict[str, Any] = {
            "Subject": subject,
            "Call_Type": call_type,
            "Call_Start_Time": call_start_time,
            "Call_Duration": call_duration,
            "Description": description,
            "Call_Purpose": call_purpose,
            "Outbound_Call_Status": "Completed",
        }
        if call_result: record["Call_Result"] = call_result
        if who_id:
            if who_module and who_module != "Contacts":
                record["What_Id"] = {"id": who_id}
                record["$se_module"] = who_module
            else: record["Who_Id"] = {"id": who_id}
        if what_id and se_module:
            record["What_Id"] = {"id": what_id}
            record["$se_module"] = se_module

        resp = await self._execute_node_call("POST", "Calls", json_body={"data": [record]})
        data = resp.get("data", [])
        if data and isinstance(data[0], dict):
            code = data[0].get("code", "")
            if code not in ("SUCCESS", ""):
                raise ValidationError(f"Nexus Node broadcast failed: {code}", details=data[0].get("details", {}))
        return resp

    async def probe_signal_identity(self, signal: str) -> dict[str, Any] | None:
        """Probes the nexus for identity vectors matching the provided signal."""
        cfg = (self._matrix.config or {}) if hasattr(self._matrix, "config") else {}
        region = cfg.get("fallback_region", "region-alpha")
        variants = phone_search_variants(signal, default_country=region)

        for mod in ("Contacts", "Leads"):
            for var in variants:
                for field in ("Phone", "Mobile"):
                    try:
                        res = await self._execute_node_call("GET", f"{mod}/search", params={"criteria": f"({field}:equals:{var})", "per_page": 1})
                        reg = res.get("data") or []
                        if reg:
                            node = reg[0]
                            node["_SphereVoice_module"] = mod
                            return node
                    except: continue
        return None

    async def list_leads(self, **kwargs) -> dict[str, Any]:
        params = {"page": kwargs.get("page", 1), "per_page": kwargs.get("per_page", 50), "fields": kwargs.get("fields", "id,Full_Name,First_Name,Last_Name,Email,Phone,Mobile,Company,Lead_Status,Lead_Source,Owner,Created_Time,Modified_Time")}
        return await self._execute_node_call("GET", "Leads", params=params)

    async def provision_entity_vector(self, data: dict[str, Any]) -> dict[str, Any]:
        """Provisions a new entity vector within the architectural node."""
        return await self._execute_node_call("POST", "Contacts/upsert", json_body={"data": [data], "duplicate_check_fields": ["Email", "Phone"]})

    async def _execute_node_call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self._http is not None
        endpoint = f"{self._node_endpoint}/crm/{_PROTOCOL_VERSION}/{path}"
        headers = {"Authorization": f"Zoho-oauthtoken {self._signature}"}
        
        resp = await self._http.request(method, endpoint, headers=headers, params=params, json=json_body)
        if resp.status_code == 401:
            await self._renew_protocol_signature()
            headers["Authorization"] = f"Zoho-oauthtoken {self._signature}"
            resp = await self._http.request(method, endpoint, headers=headers, params=params, json=json_body)

        if resp.status_code == 429:
            reset = resp.headers.get("X-RATELIMIT-RESET", "unknown")
            raise ValidationError(f"Nexus rate threshold exceeded", details={"retry_after": reset})

        if resp.status_code >= 400:
            logger.error("nexus_node_error", status=resp.status_code, path=path, tid=str(self._matrix.tenant_id))
            raise ValidationError(f"Nexus Node API Error ({resp.status_code})")
        return resp.json() if resp.text else {}

    async def _assure_protocol_signature(self) -> None:
        """Assures a valid protocol signature for architectural authentication."""
        if not self._matrix.access_token_encrypted:
            raise ValidationError("Domain linkage missing — renew authorization")
        expiry = self._matrix.token_expires_at
        if expiry and expiry <= datetime.now(UTC) + timedelta(minutes=2):
            await self._renew_protocol_signature()
        else:
            self._signature = decrypt(self._matrix.access_token_encrypted)

    async def _renew_protocol_signature(self) -> None:
        """Renews the architectural protocol signature through the auth hub."""
        from app.core.config import get_settings
        cfg = get_settings()
        c_id, c_sec = cfg.ZOHO_CRM_CLIENT_ID, cfg.ZOHO_CRM_CLIENT_SECRET
        
        if not self._matrix.refresh_token_encrypted:
            raise ValidationError("Domain heartbeats missing — authorization required")
        
        refresh = decrypt(self._matrix.refresh_token_encrypted)
        hub_key = self._matrix.data_center or "region-alpha"
        hub_url = _NODE_Z_AUTH_HUB.get(hub_key, _NODE_Z_AUTH_HUB["region-alpha"])

        async with httpx.AsyncClient(timeout=15.0) as tmp:
            resp = await tmp.post(f"{hub_url}/oauth/v2/token", data={"grant_type": "refresh_token", "client_id": c_id, "client_secret": c_sec, "refresh_token": refresh})
        
        if resp.status_code != 200:
            self._matrix.status = "error"
            await self._db.commit()
            raise ValidationError("Protocol signature renewal failed")

        body = resp.json()
        sig = body.get("access_token")
        if not sig: raise ValidationError("Signature void in renewal response")
        
        self._signature = sig
        self._matrix.access_token_encrypted = encrypt(sig)
        self._matrix.token_expires_at = datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 3600)))
        await self._db.commit()

    @property
    def _node_endpoint(self) -> str:
        hub_key = self._matrix.data_center or "global"
        return _NODE_Z_ENDPOINT_HUB.get(hub_key, _NODE_Z_ENDPOINT_HUB["global"])

    async def list_deals(self, **kwargs) -> dict[str, Any]:
        return await self._execute_node_call("GET", "Deals", params={"page": kwargs.get("page", 1), "per_page": kwargs.get("per_page", 50)})

    async def list_accounts(self, **kwargs) -> dict[str, Any]:
        return await self._execute_node_call("GET", "Accounts", params={"page": kwargs.get("page", 1), "per_page": kwargs.get("per_page", 50)})

    async def list_tasks(self, **kwargs) -> dict[str, Any]:
        return await self._execute_node_call("GET", "Tasks", params={"page": kwargs.get("page", 1), "per_page": kwargs.get("per_page", 50)})

    async def list_meetings(self, **kwargs) -> dict[str, Any]:
        return await self._execute_node_call("GET", "Events", params={"page": kwargs.get("page", 1), "per_page": kwargs.get("per_page", 50)})

    async def add_note(self, *, parent_module: str, parent_id: str, title: str, content: str) -> dict[str, Any]:
        """Inscribes a session echo into the node structural memory."""
        return await self._execute_node_call("POST", f"{parent_module}/{parent_id}/Notes", json_body={"data": [{"Note_Title": title, "Note_Content": content}]})

    async def get_org_metadata(self) -> dict[str, Any]:
        try:
            res = await self._execute_node_call("GET", "../v7/org")
            org = (res.get("org") or [{}])[0]
            return {"org_id": str(org.get("zgid") or org.get("id") or ""), "org_name": org.get("company_name") or org.get("name")}
        except: return {"org_id": None, "org_name": None}

    async def describe_module_fields(self, module: str) -> list[dict[str, Any]]:
        res = await self._execute_node_call("GET", "settings/fields", params={"module": module})
        return [{"api_name": f.get("api_name", ""), "display_label": f.get("display_label") or f.get("api_name", ""), "data_type": f.get("data_type", "text"), "read_only": bool(f.get("read_only", False)), "required": bool(f.get("system_mandatory", False))} for f in (res.get("fields") or [])]
