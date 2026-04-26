"""Google Sheets API client — async wrapper with retry & connection pooling.

All calls go through the Google Sheets v4 REST API.
Token management is delegated to GoogleOAuthService.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.google._http import GoogleAPIError, google_request
from app.modules.integrations.google.oauth import GoogleOAuthService
from app.modules.integrations.models import TenantIntegration

logger = structlog.get_logger(__name__)

_SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
_DRIVE_API = "https://www.googleapis.com/drive/v3/files"


class GoogleSheetsClient:
    """Async Google Sheets v4 client with automatic token refresh.

    Features:
    - Connection-pooled HTTP (shared across calls)
    - Exponential-backoff retry for 429 / 5xx
    - Structured ``GoogleAPIError`` for all failures
    - Pagination for list endpoints

    Usage::

        client = GoogleSheetsClient(db, integration)
        sheets = await client.list_spreadsheets()
        rows   = await client.read_rows(spreadsheet_id, "Sheet1!A1:Z100")
        await   client.append_rows(spreadsheet_id, "Sheet1", [["a", "b"]])
    """

    def __init__(self, db: AsyncSession, integration: TenantIntegration) -> None:
        self._db = db
        self._integration = integration

    async def _get_headers(self) -> dict[str, str]:
        token = await GoogleOAuthService.get_valid_access_token(self._db, self._integration)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── Spreadsheet discovery (via Drive API) ────────────────

    async def list_spreadsheets(
        self,
        *,
        max_results: int = 50,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """List Google Sheets files visible to the connected account.

        Uses the Drive API with mimeType filter.  Automatically paginates
        when ``max_results`` exceeds a single page (100 items).
        """
        headers = await self._get_headers()
        q = "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        if query:
            safe_query = query.replace("'", "\\'")
            q += f" and name contains '{safe_query}'"

        all_files: list[dict[str, Any]] = []
        page_token: str | None = None

        while len(all_files) < max_results:
            page_size = min(max_results - len(all_files), 100)
            params: dict[str, Any] = {
                "q": q,
                "pageSize": page_size,
                "fields": "nextPageToken,files(id,name,modifiedTime,webViewLink)",
                "orderBy": "modifiedTime desc",
            }
            if page_token:
                params["pageToken"] = page_token

            resp = await google_request(
                "GET", _DRIVE_API, headers=headers, params=params,
            )
            data = resp.json()
            all_files.extend(data.get("files", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return all_files[:max_results]

    # ── Spreadsheet metadata ─────────────────────────────────

    async def get_spreadsheet(
        self,
        spreadsheet_id: str,
    ) -> dict[str, Any]:
        """Fetch spreadsheet metadata (title, sheets list, etc.)."""
        headers = await self._get_headers()
        resp = await google_request(
            "GET",
            f"{_SHEETS_API}/{spreadsheet_id}",
            headers=headers,
            params={"fields": "spreadsheetId,properties,sheets.properties"},
        )
        return resp.json()

    # ── Read ─────────────────────────────────────────────────

    async def read_rows(
        self,
        spreadsheet_id: str,
        range_: str,
    ) -> list[list[Any]]:
        """Read rows from a range (e.g. ``Sheet1!A1:Z100``).

        Returns a list of rows, each row being a list of cell values.
        """
        headers = await self._get_headers()
        resp = await google_request(
            "GET",
            f"{_SHEETS_API}/{spreadsheet_id}/values/{range_}",
            headers=headers,
        )
        return resp.json().get("values", [])

    async def read_rows_with_headers(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        range_: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read rows and return them as list of dicts keyed by the header row.

        If ``range_`` is omitted, reads the entire sheet (``Sheet1!A:ZZ``).

        Returns::

            [{"Name": "Alice", "Phone": "555-0100"}, ...]
        """
        if range_ is None:
            range_ = f"{sheet_name}!A:ZZ"
        rows = await self.read_rows(spreadsheet_id, range_)
        if len(rows) < 2:
            return []
        headers = [str(h).strip() for h in rows[0]]
        return [
            {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            for row in rows[1:]
        ]

    # ── Write ────────────────────────────────────────────────

    async def append_rows(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: list[list[Any]],
    ) -> dict[str, Any]:
        """Append rows after the last occupied row in the sheet."""
        headers = await self._get_headers()
        range_ = f"{sheet_name}!A1"
        body = {"values": rows}
        resp = await google_request(
            "POST",
            f"{_SHEETS_API}/{spreadsheet_id}/values/{range_}:append",
            headers=headers,
            json_body=body,
            params={
                "valueInputOption": "USER_ENTERED",
                "insertDataOption": "INSERT_ROWS",
            },
        )
        result = resp.json()
        logger.info(
            "google_sheets_rows_appended",
            spreadsheet_id=spreadsheet_id,
            sheet=sheet_name,
            rows_added=len(rows),
            integration_id=str(self._integration.id),
        )
        return result

    async def append_dicts(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        records: list[dict[str, Any]],
        *,
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append dict records aligned to the sheet's header row.

        If ``columns`` is provided, it defines the column order explicitly.
        Otherwise, the header row is read from the sheet to determine order.
        This ensures dict keys are written to the correct columns.
        """
        if not columns:
            header_rows = await self.read_rows(spreadsheet_id, f"{sheet_name}!1:1")
            if not header_rows:
                raise GoogleAPIError(
                    0, "missing_headers",
                    f"Sheet '{sheet_name}' has no header row to align dict keys",
                )
            columns = [str(h).strip() for h in header_rows[0]]

        rows = [
            [record.get(col, "") for col in columns]
            for record in records
        ]
        return await self.append_rows(spreadsheet_id, sheet_name, rows)

    async def update_rows(
        self,
        spreadsheet_id: str,
        range_: str,
        rows: list[list[Any]],
    ) -> dict[str, Any]:
        """Overwrite a specific range with new values."""
        headers = await self._get_headers()
        body = {"values": rows}
        resp = await google_request(
            "PUT",
            f"{_SHEETS_API}/{spreadsheet_id}/values/{range_}",
            headers=headers,
            json_body=body,
            params={"valueInputOption": "USER_ENTERED"},
        )
        return resp.json()

    async def batch_update_values(
        self,
        spreadsheet_id: str,
        data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Write multiple ranges in a single request.

        ``data`` is a list of ``{"range": "Sheet1!A1:C2", "values": [[...], ...]}``.
        Uses Google's ``batchUpdate`` endpoint for efficiency at scale.
        """
        headers = await self._get_headers()
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": data,
        }
        resp = await google_request(
            "POST",
            f"{_SHEETS_API}/{spreadsheet_id}/values:batchUpdate",
            headers=headers,
            json_body=body,
        )
        return resp.json()

    async def clear_range(
        self,
        spreadsheet_id: str,
        range_: str,
    ) -> dict[str, Any]:
        """Clear all values in a range (preserves formatting)."""
        headers = await self._get_headers()
        resp = await google_request(
            "POST",
            f"{_SHEETS_API}/{spreadsheet_id}/values/{range_}:clear",
            headers=headers,
            json_body={},
        )
        return resp.json()
