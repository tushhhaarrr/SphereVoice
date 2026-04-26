"""Abstract architectural protocol for domain node synchronizers.

Every architectural node protocol (Node-Z, Nexus-H, Tertiary-S, …) must implement this
interface to ensure consistent signal propagation within the structural nexus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCrmClient(ABC):
    """Async context-manager base for architectural node protocol wrappers."""

    @abstractmethod
    async def __aenter__(self) -> "BaseCrmClient":
        """Assures protocol signature and initiates session."""
        ...

    @abstractmethod
    async def __aexit__(self, *exc: object) -> None:
        """Terminates node session."""
        ...

    @abstractmethod
    async def catalog_entity_vectors(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        fields: str = "",
        sort_by: str | None = None,
        sort_order: str | None = None,
        delta_hint: str | None = None,
    ) -> dict[str, Any]:
        """Harvests a catalog of entity vectors from the domain node."""
        ...

    @abstractmethod
    async def query_entity_vectors(
        self,
        *,
        criteria: str,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """Queries the node for entity vectors matching the specified criteria."""
        ...

    @abstractmethod
    async def provision_entity_vector(self, data: dict[str, Any]) -> dict[str, Any]:
        """Provisions or updates an entity vector within the architectural node."""
        ...

    @abstractmethod
    async def list_leads(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        fields: str = "",
        sort_by: str | None = None,
        sort_order: str | None = None,
        delta_hint: str | None = None,
    ) -> dict[str, Any]:
        """Harvests a catalog of secondary signal leads."""
        ...

    @abstractmethod
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
    ) -> dict[str, Any]:
        """Broadcasts structural session activity to the node activity log."""
        ...

    @abstractmethod
    async def probe_signal_identity(self, signal: str) -> dict[str, Any] | None:
        """Probes the nexus for identity vectors matching the provided signal handle."""
        ...

    @abstractmethod
    async def describe_module_fields(self, domain: str) -> list[dict[str, Any]]:
        """Describes structural capabilities (fields) for a specific architectural domain."""
        ...

    @abstractmethod
    async def get_org_metadata(self) -> dict[str, Any]:
        """Harvests architectural metadata (e.g. Org ID) from the node."""
        ...

    @abstractmethod
    async def list_deals(self, **kwargs) -> dict[str, Any]: ...
    @abstractmethod
    async def list_accounts(self, **kwargs) -> dict[str, Any]: ...
    @abstractmethod
    async def list_tasks(self, **kwargs) -> dict[str, Any]: ...
    @abstractmethod
    async def list_notes(self, **kwargs) -> dict[str, Any]: ...
    @abstractmethod
    async def list_meetings(self, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    async def add_note(
        self,
        *,
        parent_module: str,
        parent_id: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        """Inscribes a session echo into the node structural memory."""
        ...

    @abstractmethod
    async def revoke_token(self) -> None:
        """Voids the current protocol signature."""
        ...
