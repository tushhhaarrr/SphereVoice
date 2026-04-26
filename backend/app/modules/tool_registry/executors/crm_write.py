"""CRM Write executor — writes data to a CRM via the configured integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)


class CrmWriteExecutor:
    """Execute a CRM write tool — update fields on a CRM record during a live call.

    The tool's ``execution_config`` may contain:
    - ``crm_type``: ``"zoho"`` | ``"hubspot"`` (default: ``"zoho"``)
    - ``allowed_fields``: list of CRM field api_names the LLM is allowed to update
    - ``confirm_before_write``: if True, the LLM should ask user confirmation first

    The ``call_context`` provides:
    - ``caller_crm_id``: The CRM record ID from pre-call enrichment
    - ``caller_crm_module``: The CRM module (e.g. ``"Leads"``, ``"Contacts"``)
    - ``tenant_id``: Used to look up the CRM integration

    Arguments from the LLM:
    - ``field_name``: The CRM field to update
    - ``value``: The new value to set
    """

    async def execute(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}

        field_name: str = arguments.get("field_name", "")
        value: str = arguments.get("value", "")

        if not field_name or not value:
            return {
                "success": False,
                "error": "Both field_name and value are required",
                "tool": tool.name,
            }

        # Safety: check allowed fields
        raw_allowed = config.get("allowed_fields", [])
        if isinstance(raw_allowed, str):
            allowed_fields = [f.strip() for f in raw_allowed.splitlines() if f.strip()]
        else:
            allowed_fields = list(raw_allowed)
        if allowed_fields and field_name not in allowed_fields:
            logger.warning(
                "crm_write_field_not_allowed",
                tool_name=tool.name,
                field_name=field_name,
                allowed=allowed_fields,
            )
            return {
                "success": False,
                "error": f"Field '{field_name}' is not in the allowed list for this agent",
                "tool": tool.name,
            }

        # Get CRM record context from the call
        crm_record_id: str = call_context.get("caller_crm_id", "")
        crm_module: str = call_context.get("caller_crm_module", "Leads")
        tenant_id: str = call_context.get("tenant_id", "")

        if not crm_record_id:
            return {
                "success": False,
                "error": "No CRM record linked to this call — cannot update field",
                "tool": tool.name,
            }

        if not tenant_id:
            return {
                "success": False,
                "error": "No tenant context — cannot access CRM",
                "tool": tool.name,
            }

        try:
            return await self._write_to_zoho(
                tenant_id=tenant_id,
                crm_module=crm_module,
                crm_record_id=crm_record_id,
                field_name=field_name,
                value=value,
                tool_name=tool.name,
                call_id=call_context.get("call_id"),
            )
        except Exception as exc:
            logger.exception(
                "crm_write_executor_error",
                tool_name=tool.name,
                field_name=field_name,
                error=str(exc),
            )
            return {
                "success": False,
                "error": f"CRM update failed: {exc}",
                "tool": tool.name,
            }

    async def _write_to_zoho(
        self,
        *,
        tenant_id: str,
        crm_module: str,
        crm_record_id: str,
        field_name: str,
        value: str,
        tool_name: str,
        call_id: str | None,
    ) -> dict[str, Any]:
        """Update a single field on a Zoho CRM record."""
        from uuid import UUID

        from app.core.database import async_session_factory
        from app.modules.integrations.crm.factory import resolve_nexus_protocol
        from app.modules.integrations.models import CrmIntegration, CrmSyncLog

        async with async_session_factory() as db:
            # Find the tenant's CRM integration
            result = await db.execute(
                select(CrmIntegration).where(
                    CrmIntegration.tenant_id == UUID(tenant_id),
                    CrmIntegration.provider == "zoho",
                    CrmIntegration.status == "connected",
                )
            )
            integration = result.scalar_one_or_none()
            if integration is None:
                return {
                    "success": False,
                    "error": "No connected CRM integration found for this tenant",
                    "tool": tool_name,
                }

            async with resolve_nexus_protocol(integration.provider, db, integration) as client:
                # Use the generic _request method to do a PUT update
                update_data = {field_name: value}
                api_response = await client._request(
                    "PUT",
                    f"{crm_module}/{crm_record_id}",
                    json_body={"data": [update_data]},
                )

            # Log the CRM sync operation
            sync_log = CrmSyncLog(
                tenant_id=UUID(tenant_id),
                integration_id=integration.id,
                sync_type="field_update",
                direction="outbound",
                status="success",
                details={
                    "module": crm_module,
                    "record_id": crm_record_id,
                    "field": field_name,
                    "value": value,
                    "source": "mid_call_tool",
                    "call_id": call_id,
                },
            )
            db.add(sync_log)
            await db.commit()

        logger.info(
            "crm_write_success",
            tool_name=tool_name,
            module=crm_module,
            record_id=crm_record_id,
            field=field_name,
            call_id=call_id,
        )

        return {
            "success": True,
            "tool": tool_name,
            "module": crm_module,
            "record_id": crm_record_id,
            "field_updated": field_name,
            "new_value": value,
            "status": "confirmed",
        }

