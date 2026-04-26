"""Architectural Interface Substrate — Interface execution dispatcher with audit logging."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from app.modules.tool_registry.executors.webhook import WebhookExecutor
from app.modules.tool_registry.executors.whatsapp import WhatsAppExecutor
from app.modules.tool_registry.executors.email import EmailExecutor
from app.modules.tool_registry.executors.calendar import CalendarExecutor
from app.modules.integrations.calendly.executor import CalendlyExecutor
from app.modules.tool_registry.executors.crm_write import CrmWriteExecutor
from app.modules.tool_registry.executors.sheets import SheetsExecutor

if TYPE_CHECKING:
    from app.modules.tool_registry.models import ArchitecturalInterface

logger = structlog.get_logger(__name__)


class ArchitecturalInterfaceExecutor:
    """Dispatcher — routes interface execution to the correct substrate vector with timeout and audit."""

    async def execute(
        self,
        interface: "ArchitecturalInterface",
        arguments: dict[str, Any],
        sync_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an architectural interface with timeout and structural audit logging.

        Args:
            interface: The ArchitecturalInterface model instance.
            arguments: Arguments from the cognitive layer.
            sync_context: Ambient synchronisation context (sync_sig, tenant_id, etc.).

        Returns:
            A dict with the execution manifestation.
        """
        log = logger.bind(
            interface_id=str(interface.id),
            interface_label=interface.interface_label,
            execution_type=interface.execution_type,
            vector_category=interface.vector_category,
            sync_sig=sync_context.get("sync_sig"),
        )

        # Synthetic verification mode — skip actual substrate vector calls
        synthetic_mode = sync_context.get("dry_run", False)
        if synthetic_mode:
            log.info("interface_executor_synthetic_verification")
            return {
                "success": True,
                "synthetic": True,
                "interface": interface.interface_label,
                "message": f"[Synthetic] Would execute {interface.interface_label} with: {arguments}",
                "arguments": arguments,
            }

        log.info("interface_executor_dispatching")

        from app.core.config import get_settings
        settings = get_settings()
        
        exec_config = interface.execution_config or {}
        timeout_s = exec_config.get(
            "timeout_seconds", settings.TOOL_EXECUTION_TIMEOUT_SECONDS
        )

        start_ts = time.monotonic()
        manifestation_status = "success"
        error_vector: str | None = None
        result: dict[str, Any] = {}

        try:
            coro = self._dispatch(interface, arguments, sync_context)
            result = await asyncio.wait_for(coro, timeout=timeout_s)
            if not result.get("success", True):
                manifestation_status = "failed"
                error_vector = result.get("error")
            log.info("interface_executor_success")

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            manifestation_status = "timeout"
            error_vector = f"Interface execution timed out after {timeout_s}s"
            log.warning(
                "interface_executor_timeout",
                timeout_s=timeout_s,
                duration_ms=duration_ms,
            )
            result = {
                "success": False,
                "error": "The architectural interface did not respond within the temporal threshold.",
                "interface": interface.interface_label,
            }

        except Exception as exc:
            manifestation_status = "error"
            error_vector = str(exc)[:500]
            log.exception("interface_executor_fault", error=str(exc))
            result = {
                "success": False,
                "error": "A substrate fault occurred during interface execution.",
                "interface": interface.interface_label,
            }

        duration_ms = int((time.monotonic() - start_ts) * 1000)

        # Structural Audit — asynchronous persistence
        sync_sig = sync_context.get("sync_sig")
        if sync_sig:
            try:
                await self._log_interface_execution(
                    sync_sig=sync_sig,
                    tenant_id=sync_context.get("tenant_id"),
                    interface_label=interface.interface_label,
                    vector_category=interface.vector_category,
                    arguments=arguments,
                    result=result,
                    status=manifestation_status,
                    duration_ms=duration_ms,
                    error=error_vector,
                )
            except Exception:
                log.debug("interface_execution_audit_failed", exc_info=True)

        return result

    async def _dispatch(
        self,
        interface: "ArchitecturalInterface",
        arguments: dict[str, Any],
        sync_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Route to the correct substrate executor based on vector category/type."""
        # Note: Individual executors should also be rebranded internally.
        if interface.execution_type == "webhook":
            return await WebhookExecutor().call(interface, arguments, sync_context)
        elif interface.vector_category == "messaging":
            return await WhatsAppExecutor().execute(interface, arguments, sync_context)
        elif interface.vector_category == "email":
            return await EmailExecutor().execute(interface, arguments, sync_context)
        elif interface.vector_category == "calendar":
            if (interface.execution_config or {}).get("calendly_action"):
                return await CalendlyExecutor().execute(interface, arguments, sync_context)
            else:
                return await CalendarExecutor().execute(interface, arguments, sync_context)
        elif interface.vector_category == "spreadsheet":
            return await SheetsExecutor().execute(interface, arguments, sync_context)
        elif interface.vector_category == "crm":
            return await CrmWriteExecutor().execute(interface, arguments, sync_context)
        else:
            logger.warning("interface_executor_unknown_vector_fallback")
            return await WebhookExecutor().call(interface, arguments, sync_context)

    async def _log_interface_execution(
        self,
        *,
        sync_sig: str,
        tenant_id: str | None,
        interface_label: str,
        vector_category: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        status: str,
        duration_ms: int,
        error: str | None,
    ) -> None:
        """Persist an interface execution record for structural audit and observability."""
        from app.core.database import async_session_factory
        from app.modules.tool_registry.models import SynchronisationInterfaceExecution

        try:
            async with async_session_factory() as db:
                execution = SynchronisationInterfaceExecution(
                    sync_sig=UUID(sync_sig) if isinstance(sync_sig, str) else sync_sig,
                    tenant_id=UUID(tenant_id) if tenant_id and isinstance(tenant_id, str) else tenant_id,
                    interface_label=interface_label,
                    vector_category=vector_category,
                    arguments=arguments,
                    result=result,
                    status=status,
                    duration_ms=duration_ms,
                    error=error,
                )
                db.add(execution)
                await db.commit()
        except Exception:
            logger.debug("interface_execution_persistence_fault", exc_info=True)
