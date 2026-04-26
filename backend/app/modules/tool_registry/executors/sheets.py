"""Google Sheets executor — read & write to Google Sheets during live calls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from app.modules.tool_registry.models import TenantTool

logger = structlog.get_logger(__name__)


class SheetsExecutor:
    """Execute sheets tools during live voice calls.

    Supports multiple actions via the ``action`` field in arguments
    (or ``execution_config.default_action``):

    - ``append`` (default) — append a row to a sheet
    - ``read`` — read rows from a sheet (returns data to LLM)

    ``execution_config`` must specify:
    - ``spreadsheet_id`` — the Google spreadsheet ID
    - ``sheet_name``     — the tab name (default: ``"Sheet1"``)
    - ``columns``        — ordered list of column names for dict→row alignment
                           (optional; if absent, reads header row from sheet)

    The tool must be linked to a TenantIntegration with provider ``google_sheets``.
    """

    async def execute(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        action = arguments.get("action", config.get("default_action", "append"))

        if action == "read":
            return await self._handle_read(tool, arguments, call_context)
        return await self._handle_append(tool, arguments, call_context)

    # ── Append ───────────────────────────────────────────────

    async def _handle_append(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        spreadsheet_id: str = config.get("spreadsheet_id", "")
        sheet_name: str = config.get("sheet_name", "Sheet1")
        row_data_field: str = config.get("row_data_field", "row_data")
        raw_columns = config.get("columns")

        # Normalise columns: accept [{name, description}, ...] or ["Name", ...]
        columns: list[str] | None = None
        if raw_columns:
            if isinstance(raw_columns[0], dict):
                columns = [c["name"] for c in raw_columns if c.get("name")]
            else:
                columns = list(raw_columns)

        row_data = arguments.get(row_data_field)
        if row_data is None:
            return {
                "success": False,
                "error": f"Missing required field: {row_data_field}",
                "tool": tool.name,
            }

        if not spreadsheet_id:
            return {
                "success": False,
                "error": "spreadsheet_id not configured in execution_config",
                "tool": tool.name,
            }

        if not tool.integration_id:
            logger.info(
                "sheets_append_queued_no_integration",
                tool_name=tool.name,
                call_id=call_context.get("call_id"),
            )
            return {
                "success": True,
                "tool": tool.name,
                "status": "queued",
                "message": "No Sheets integration linked — row logged but not sent",
            }

        try:
            return await self._append_to_sheet(
                tool=tool,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                row_data=row_data,
                columns=columns,
                call_context=call_context,
            )
        except Exception as exc:
            logger.exception(
                "sheets_google_api_error",
                tool_name=tool.name,
                error=str(exc),
            )
            return {
                "success": False,
                "error": f"Failed to append to sheet: {exc}",
                "tool": tool.name,
            }

    # ── Read ─────────────────────────────────────────────────

    async def _handle_read(
        self,
        tool: "TenantTool",
        arguments: dict[str, Any],
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = tool.execution_config or {}
        spreadsheet_id: str = config.get("spreadsheet_id", "")
        sheet_name: str = config.get("sheet_name", "Sheet1")

        if not spreadsheet_id:
            return {
                "success": False,
                "error": "spreadsheet_id not configured in execution_config",
                "tool": tool.name,
            }

        if not tool.integration_id:
            return {
                "success": False,
                "error": "No Sheets integration linked — cannot read",
                "tool": tool.name,
            }

        range_ = arguments.get("range", f"{sheet_name}!A:ZZ")
        max_rows: int = min(int(arguments.get("max_rows", 50)), 200)

        try:
            ctx = await self._get_client_ctx(tool, call_context)
            async with ctx as client:
                rows = await client.read_rows(spreadsheet_id, range_)

            # Cap to max_rows + header for LLM context limits
            if len(rows) > max_rows + 1:
                rows = rows[:max_rows + 1]

            # If there's a header row, return as list of dicts for LLM readability
            if len(rows) >= 2:
                headers = [str(h).strip() for h in rows[0]]
                records = [
                    {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
                    for row in rows[1:]
                ]
                return {
                    "success": True,
                    "tool": tool.name,
                    "records": records,
                    "row_count": len(records),
                    "columns": headers,
                }
            else:
                return {
                    "success": True,
                    "tool": tool.name,
                    "records": [],
                    "row_count": 0,
                    "raw_rows": rows,
                }
        except Exception as exc:
            logger.exception(
                "sheets_read_error",
                tool_name=tool.name,
                error=str(exc),
            )
            return {
                "success": False,
                "error": f"Failed to read from sheet: {exc}",
                "tool": tool.name,
            }

    # ── Helpers ──────────────────────────────────────────────

    async def _get_client_ctx(
        self,
        tool: "TenantTool",
        call_context: dict[str, Any],
    ) -> Any:
        """Context-manager that yields (GoogleSheetsClient, db_session)."""
        from contextlib import asynccontextmanager

        from app.core.database import async_session_factory
        from app.modules.integrations.google.sheets_client import GoogleSheetsClient
        from app.modules.integrations.models import TenantIntegration

        @asynccontextmanager
        async def _ctx():
            tenant_id = call_context.get("tenant_id")
            async with async_session_factory() as session:
                query = select(TenantIntegration).where(
                    TenantIntegration.id == tool.integration_id,
                )
                if tenant_id:
                    query = query.where(TenantIntegration.tenant_id == tenant_id)
                result = await session.execute(query)
                integration = result.scalar_one_or_none()
                if integration is None:
                    raise ValueError("Sheets integration not found — please reconnect Google Sheets")
                yield GoogleSheetsClient(session, integration)

        return _ctx()

    async def _append_to_sheet(
        self,
        tool: "TenantTool",
        spreadsheet_id: str,
        sheet_name: str,
        row_data: Any,
        columns: list[str] | None,
        call_context: dict[str, Any],
    ) -> dict[str, Any]:
        from app.core.database import async_session_factory
        from app.modules.integrations.google.sheets_client import GoogleSheetsClient
        from app.modules.integrations.models import TenantIntegration

        tenant_id = call_context.get("tenant_id")
        async with async_session_factory() as db:
            query = select(TenantIntegration).where(
                TenantIntegration.id == tool.integration_id,
            )
            if tenant_id:
                query = query.where(TenantIntegration.tenant_id == tenant_id)
            result = await db.execute(query)
            integration = result.scalar_one_or_none()
            if integration is None:
                return {
                    "success": False,
                    "error": "Sheets integration not found — please reconnect Google Sheets",
                    "tool": tool.name,
                }

            client = GoogleSheetsClient(db, integration)

            if isinstance(row_data, dict):
                # Use header-aware append for proper column alignment
                await client.append_dicts(
                    spreadsheet_id, sheet_name, [row_data], columns=columns,
                )
            else:
                # Raw list or single value
                row = row_data if isinstance(row_data, list) else [str(row_data)]
                await client.append_rows(spreadsheet_id, sheet_name, [row])

        logger.info(
            "sheets_row_appended_via_google",
            tool_name=tool.name,
            spreadsheet_id=spreadsheet_id,
            sheet=sheet_name,
            call_id=call_context.get("call_id"),
        )

        return {
            "success": True,
            "tool": tool.name,
            "status": "appended",
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
        }
