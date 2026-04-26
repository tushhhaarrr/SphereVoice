"""Backfill shared provider secrets from platform settings into Key Vault."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session_factory
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.providers.service import ProviderService


async def main() -> None:
    async with async_session_factory() as session:
        result = await ProviderService.sync_shared_provider_secrets_from_settings(session)
        await session.commit()

    synced = ", ".join(result["synced"]) or "none"
    missing = ", ".join(result["missing"]) or "none"
    print(f"synced={synced}")
    print(f"missing={missing}")


if __name__ == "__main__":
    asyncio.run(main())