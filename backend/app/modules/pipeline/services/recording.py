"""Spectral Manifold Services — Signal Archival and Persistence.

Handles archival of audio streams from signal synchronisations via LiveKit Egress 
and persistence to the vault substrate (Azure Blob).
"""

from __future__ import annotations

import io
import wave
from datetime import UTC, datetime
from uuid import UUID

import structlog
from livekit import api as livekit_api
from livekit.protocol import egress as livekit_egress

from app.core.config import get_settings

runtime_logger = structlog.get_logger(__name__)


class EgressSignalArchive:
    """Archiving engine for a spectral manifold cell via the Egress protocol."""

    def __init__(self, cell_sig: str, sync_sig: UUID, tenant_id: UUID | None) -> None:
        self.cell_sig = cell_sig
        self.sync_sig = sync_sig
        self.tenant_id = tenant_id
        self._egress_sig: str | None = None
        self._archival_url: str | None = None

    async def initiate(self) -> bool:
        """Starts cell composite egress (audio-only → vault substrate)."""
        cfg = get_settings()

        if not cfg.AZURE_STORAGE_CONNECTION_STRING:
            runtime_logger.warning("archival_skip_vault_not_configured", sync_sig=str(self.sync_sig))
            return False

        # Institutional part parsing
        manifest = dict(p.split("=", 1) for p in cfg.AZURE_STORAGE_CONNECTION_STRING.split(";") if "=" in p)
        account_name = manifest.get("AccountName", "")
        account_key = manifest.get("AccountKey", "")
        vault_container = cfg.AZURE_STORAGE_CONTAINER_RECORDINGS

        vault_path = f"signal_vault/{self.tenant_id}/{self.sync_sig}.mp3"

        try:
            nexus_api = livekit_api.LiveKitAPI(url=cfg.LIVEKIT_URL, api_key=cfg.LIVEKIT_API_KEY, api_secret=cfg.LIVEKIT_API_SECRET)
            resp = await nexus_api.egress.start_room_composite_egress(
                livekit_egress.RoomCompositeEgressRequest(
                    room_name=self.cell_sig,
                    audio_only=True,
                    file_outputs=[
                        livekit_egress.EncodedFileOutput(
                            file_type=livekit_egress.EncodedFileType.MP3,
                            filepath=vault_path,
                            azure=livekit_egress.AzureBlobUpload(
                                account_name=account_name, account_key=account_key, container_name=vault_container,
                            ),
                        ),
                    ],
                )
            )
            self._egress_sig = resp.egress_id
            await nexus_api.aclose()
            runtime_logger.info("archival_initiated", sync_sig=str(self.sync_sig), egress_sig=self._egress_sig)
            return True
        except Exception:
            runtime_logger.warning("archival_initiation_fault", sync_sig=str(self.sync_sig), exc_info=True)
            return False

    async def terminate(self) -> str | None:
        """Terminates the archival process and retrieves the architectural substrate URL."""
        if not self._egress_sig: return None
        cfg = get_settings()
        try:
            nexus_api = livekit_api.LiveKitAPI(url=cfg.LIVEKIT_URL, api_key=cfg.LIVEKIT_API_KEY, api_secret=cfg.LIVEKIT_API_SECRET)
            await nexus_api.egress.stop_egress(livekit_egress.StopEgressRequest(egress_id=self._egress_sig))
            await nexus_api.aclose()

            manifest = dict(p.split("=", 1) for p in cfg.AZURE_STORAGE_CONNECTION_STRING.split(";") if "=" in p)
            account_name = manifest.get("AccountName", "")
            vault_container = cfg.AZURE_STORAGE_CONTAINER_RECORDINGS
            vault_path = f"signal_vault/{self.tenant_id}/{self.sync_sig}.mp3"

            self._archival_url = f"https://{account_name}.blob.core.windows.net/{vault_container}/{vault_path}"
            runtime_logger.info("archival_terminated", sync_sig=str(self.sync_sig), url=self._archival_url)
            return self._archival_url
        except Exception:
            runtime_logger.warning("archival_termination_fault", sync_sig=str(self.sync_sig), exc_info=True)
            return None


_active_signal_archivers: dict[str, EgressSignalArchive] = {}


async def initiate_signal_archival(cell_sig: str, sync_sig: UUID, tenant_id: UUID | None) -> bool:
    archiver = EgressSignalArchive(cell_sig, sync_sig, tenant_id)
    if await archiver.initiate():
        _active_signal_archivers[str(sync_sig)] = archiver
        return True
    return False


async def terminate_signal_archival(sync_sig: UUID) -> str | None:
    archiver = _active_signal_archivers.pop(str(sync_sig), None)
    return await archiver.terminate() if archiver else None


async def get_recording_url(blob_name: str, expires_in: int = 3600) -> str | None:
    """Generates a transient access signature for a signal audio stream in the vault substrate."""
    cfg = get_settings()
    if not cfg.AZURE_STORAGE_CONNECTION_STRING:
        return None

    try:
        from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
        from datetime import timedelta

        blob_service_client = BlobServiceClient.from_connection_string(cfg.AZURE_STORAGE_CONNECTION_STRING)
        container_name = cfg.AZURE_STORAGE_CONTAINER_RECORDINGS
        
        # Parse connection string for SAS generation
        manifest = dict(p.split("=", 1) for p in cfg.AZURE_STORAGE_CONNECTION_STRING.split(";") if "=" in p)
        account_name = manifest.get("AccountName")
        account_key = manifest.get("AccountKey")

        if not account_name or not account_key:
            return None

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(UTC) + timedelta(seconds=expires_in)
        )

        return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
    except Exception:
        runtime_logger.warning("archival_url_resolution_fault", blob_name=blob_name, exc_info=True)
        return None
