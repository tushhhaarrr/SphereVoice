"""Junction Hub Logic — Cross-domain architectural synchronization.

Handles:
- Structural protocol initiation and echo resolution (Node-Z and extensible nodes)
- Encrypted signature persistence (AES-256-GCM)
- Signature cycling and node heartbeat synchronization
- Best-effort link severance 
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json as _json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.integrations.models import CrmIntegration, TenantIntegration
from app.modules.integrations.schemas import DomLinkCreate, DomLinkUpdate

logger = structlog.get_logger(__name__)
app_cfg = get_settings()

_NODE_Z_AUTH_HUB: dict[str, str] = {
    "com": "https://accounts.zoho.com",
    "eu": "https://accounts.zoho.eu",
    "in": "https://accounts.zoho.in",
    "au": "https://accounts.zoho.com.au",
    "jp": "https://accounts.zoho.jp",
    "ca": "https://accounts.zohocloud.ca",
    "uk": "https://accounts.zoho.uk",
}

_NODE_Z_PROTOCOLS = "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.ALL"
VALID_REGIONS = frozenset(_NODE_Z_AUTH_HUB.keys())


def _spawn_protocol_state(tid: UUID, uid: UUID, region: str = "in") -> str:
    """Spawns a tamper-evident protocol state for architectural handshakes."""
    nonce = secrets.token_hex(8)
    msg = f"{tid}:{uid}:{region}:{nonce}"
    enc = base64.urlsafe_b64encode(msg.encode()).decode()
    sig = hmac.new(app_cfg.JWT_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{enc}.{sig}"


def _validate_protocol_state(state: str) -> tuple[UUID, UUID, str]:
    """Validates the protocol state and extracts the embedded domain context."""
    if not state or "." not in state:
        raise ValidationError("Incomplete protocol handshake detected.")
    try:
        enc, sig = state.rsplit(".", 1)
        pad = enc + "=" * (-len(enc) % 4)
        msg = base64.urlsafe_b64decode(pad.encode()).decode()
        exp = hmac.new(app_cfg.JWT_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, exp):
            raise ValidationError("Protocol integrity violation.")
        tokens = msg.split(":")
        if len(tokens) < 3:
            raise ValidationError("Protocol payload corrupted.")
        reg = tokens[2] if len(tokens) >= 4 else "in"
        return UUID(tokens[0]), UUID(tokens[1]), reg
    except ValidationError: raise
    except Exception as exc: raise ValidationError(f"Faulty protocol resolution: {exc}")


def _resolve_node_region(server: str | None) -> str:
    """Infers the target node region from egress server metadata."""
    if not server: return "com"
    s = server.lower()
    for k in ["eu", "in", "jp", "uk"]:
        if f"zoho.{k}" in s: return k
    if "zoho.com.au" in s: return "au"
    if "zohocloud.ca" in s: return "ca"
    return "com"


class JunctionMatrix:
    """Architectural nexus for cross-domain node orchestration."""

    @staticmethod
    async def list_integrations(db: AsyncSession, tid: UUID) -> tuple[list[CrmIntegration], int]:
        res = await db.execute(select(CrmIntegration).where(CrmIntegration.tenant_id == tid).order_by(CrmIntegration.created_at.desc()))
        rows = list(res.scalars().all())
        return rows, len(rows)

    @staticmethod
    async def get_integration(db: AsyncSession, iid: UUID, tid: UUID) -> CrmIntegration:
        res = await db.execute(select(CrmIntegration).where(CrmIntegration.id == iid, CrmIntegration.tenant_id == tid))
        obj = res.scalar_one_or_none()
        if obj is None: raise NotFoundError("ArchNode", str(iid))
        return obj

    @staticmethod
    def build_zoho_auth_url(tid: UUID, uid: UUID, region: str | None = None) -> str:
        if not app_cfg.ZOHO_CRM_CLIENT_ID: raise ValidationError("Node-Z protocol not configured.")
        reg = region or app_cfg.ZOHO_CRM_DATA_CENTER
        if reg not in VALID_REGIONS: raise ValidationError(f"Target region {reg} unknown.")
        state = _spawn_protocol_state(tid, uid, reg)
        p = {
            "scope": _NODE_Z_PROTOCOLS,
            "client_id": app_cfg.ZOHO_CRM_CLIENT_ID,
            "response_type": "code",
            "access_type": "offline",
            "redirect_uri": app_cfg.ZOHO_CRM_REDIRECT_URI,
            "state": state,
            "prompt": "consent",
        }
        return f"{_NODE_Z_AUTH_HUB[reg]}/oauth/v2/auth?{urlencode(p)}"

    @staticmethod
    def build_oauth_url(provider: str, tid: UUID, uid: UUID, data_center: str | None = None) -> str:
        if provider == "zoho_crm":
            return JunctionMatrix.build_zoho_auth_url(tid, uid, data_center)
        raise ValidationError("Unsupported CRM provider")

    @staticmethod
    async def handle_oauth_callback(provider: str, db: AsyncSession, code: str, state: str, **kwargs) -> Any:
        if provider == "zoho_crm":
            return await JunctionMatrix.handle_zoho_callback(db, code, state, **kwargs)
        raise ValidationError("Unsupported CRM provider")

    @staticmethod
    async def handle_zoho_callback(
        db: AsyncSession,
        code: str,
        state: str,
        accounts_server: str | None = None,
        location: str | None = None,
    ) -> CrmIntegration:
        """Resolves Node-Z structural handshake and establishes a persistent link."""
        tid, uid, reg_hint = _validate_protocol_state(state)
        reg = _resolve_node_region(accounts_server) or reg_hint

        auth_base = _NODE_Z_AUTH_HUB.get(reg, _NODE_Z_AUTH_HUB["com"])
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{auth_base}/oauth/v2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": app_cfg.ZOHO_CRM_CLIENT_ID,
                    "client_secret": app_cfg.ZOHO_CRM_CLIENT_SECRET,
                    "redirect_uri": app_cfg.ZOHO_CRM_REDIRECT_URI,
                    "code": code,
                },
            )
        
        if resp.status_code != 200:
            raise ValidationError(f"Node-Z token exchange failed: {resp.text}")

        blob = resp.json()
        acc_token = blob.get("access_token")
        ref_token = blob.get("refresh_token")
        expiry = int(blob.get("expires_in", 3600))

        if not acc_token: raise ValidationError("Void access token in Node-Z resolution")

        res = await db.execute(select(CrmIntegration).where(CrmIntegration.tenant_id == tid, CrmIntegration.provider == "node_z_protocol"))
        matrix = res.scalar_one_or_none()
        if matrix is None:
            matrix = CrmIntegration(tenant_id=tid, provider="node_z_protocol")
            db.add(matrix)

        matrix.status = "connected"
        matrix.data_center = reg
        matrix.access_token_encrypted = encrypt(acc_token)
        if ref_token: matrix.refresh_token_encrypted = encrypt(ref_token)
        matrix.token_expires_at = datetime.now(UTC) + timedelta(seconds=expiry)
        matrix.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(matrix)

        try:
            from app.workers.domain_harvest import perform_comprehensive_harvest
            perform_comprehensive_harvest.delay(str(matrix.id))
        except: logger.warning("initial_harvest_trigger_fault", matrix_id=str(matrix.id))

        return matrix

    @staticmethod
    async def _refresh_access_token(db: AsyncSession, matrix: CrmIntegration) -> str:
        if not matrix.refresh_token_encrypted: raise ValidationError("Void refresh signature")
        ref_token = decrypt(matrix.refresh_token_encrypted)
        
        auth_base = _NODE_Z_AUTH_HUB.get(matrix.data_center, _NODE_Z_AUTH_HUB["com"])
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{auth_base}/oauth/v2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": app_cfg.ZOHO_CRM_CLIENT_ID,
                    "client_secret": app_cfg.ZOHO_CRM_CLIENT_SECRET,
                    "refresh_token": ref_token,
                },
            )
        if resp.status_code != 200:
            matrix.status = "error"
            await db.commit()
            raise ValidationError("Token refresh failure")

        blob = resp.json()
        acc = blob.get("access_token")
        if not acc: raise ValidationError("Void access token in refresh")
        matrix.access_token_encrypted = encrypt(acc)
        matrix.token_expires_at = datetime.now(UTC) + timedelta(seconds=int(blob.get("expires_in", 3600)))
        return acc

    @staticmethod
    async def sync_integration(db: AsyncSession, iid: UUID, tid: UUID) -> CrmIntegration:
        matrix = await JunctionMatrix.get_integration(db, iid, tid)
        if not matrix.access_token_encrypted: raise ValidationError("Void access signature")
        if matrix.token_expires_at and matrix.token_expires_at <= datetime.now(UTC):
            await JunctionMatrix._refresh_access_token(db, matrix)

        try:
            from app.modules.integrations.crm.factory import resolve_nexus_protocol
            async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
                meta = await client.get_org_metadata()
                if meta.get("org_id"): matrix.org_id = meta["org_id"]
                if meta.get("org_name"): matrix.org_name = meta["org_name"]
                matrix.status = "connected"
        except Exception as exc:
            matrix.status = "error"
            await db.commit()
            raise ValidationError(f"Nexus resolution fault: {exc}")

        matrix.last_synced_at = datetime.now(UTC)
        matrix.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(matrix)
        return matrix

    @staticmethod
    async def disconnect_integration(db: AsyncSession, iid: UUID, tid: UUID) -> None:
        matrix = await JunctionMatrix.get_integration(db, iid, tid)
        if matrix.access_token_encrypted:
            try:
                from app.modules.integrations.crm.factory import resolve_nexus_protocol
                async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
                    await client.revoke_token()
            except: logger.warning("nexus_revoke_fault", iid=str(iid))

        try:
            from app.modules.integrations.crm_cache_service import InventoryOrchestrator
            await InventoryOrchestrator.purge_inventory(db, iid)
        except: pass

        await db.delete(matrix)
        await db.commit()


class DomainNodeOrchestrator:
    """Orchestration service for general domain node integrations."""

    @staticmethod
    async def list_integrations(db: AsyncSession, tid: UUID) -> tuple[list[TenantIntegration], int]:
        res = await db.execute(select(TenantIntegration).where(TenantIntegration.tenant_id == tid).order_by(TenantIntegration.created_at.desc()))
        rows = list(res.scalars().all())
        return rows, len(rows)

    @staticmethod
    async def get_integration(db: AsyncSession, tid: UUID, iid: UUID) -> TenantIntegration:
        res = await db.execute(select(TenantIntegration).where(TenantIntegration.id == iid, TenantIntegration.tenant_id == tid))
        obj = res.scalar_one_or_none()
        if obj is None: raise NotFoundError("DomainNode", str(iid))
        return obj

    @staticmethod
    async def create_integration(db: AsyncSession, tid: UUID, data: DomLinkCreate) -> TenantIntegration:
        res = await db.execute(select(TenantIntegration).where(TenantIntegration.tenant_id == tid, TenantIntegration.name == data.name))
        if res.scalar_one_or_none(): raise ConflictError(f"Node '{data.name}' already exists")

        creds = encrypt(_json.dumps(data.credentials)) if data.credentials else None
        obj = TenantIntegration(
            tenant_id=tid, name=data.name, category=data.category, provider=data.provider,
            credentials_encrypted=creds, config=data.config or {},
            status=data.status or "active"
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    @staticmethod
    async def update_integration(db: AsyncSession, tid: UUID, iid: UUID, data: DomLinkUpdate) -> TenantIntegration:
        obj = await DomainNodeOrchestrator.get_integration(db, tid, iid)
        if data.name and data.name != obj.name:
            res = await db.execute(select(TenantIntegration).where(TenantIntegration.tenant_id == tid, TenantIntegration.name == data.name))
            if res.scalar_one_or_none(): raise ConflictError(f"Node '{data.name}' already exists")
            obj.name = data.name
        
        if data.status: obj.status = data.status
        if data.credentials: obj.credentials_encrypted = encrypt(_json.dumps(data.credentials))
        if data.config is not None: obj.config = data.config
        
        await db.commit()
        await db.refresh(obj)
        return obj

    @staticmethod
    async def delete_integration(db: AsyncSession, tid: UUID, iid: UUID) -> None:
        obj = await DomainNodeOrchestrator.get_integration(db, tid, iid)
        await db.delete(obj)
        await db.commit()
