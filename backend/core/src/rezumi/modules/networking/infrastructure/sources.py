"""Purpose-minimized Application Workspace adapter for Networking."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from rezumi.modules.application_workspace.application import ApplicationReference
from rezumi.modules.networking.application import NetworkingApplicationReference


class _ApplicationWorkspaceReferenceService(Protocol):
    async def get_application_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationReference: ...


class ApplicationWorkspaceNetworkingReferenceProvider:
    """Resolve only an owner-authorized application identifier and stage."""

    def __init__(self, service: _ApplicationWorkspaceReferenceService) -> None:
        self._service = service

    async def get_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> NetworkingApplicationReference | None:
        try:
            source = await self._service.get_application_reference(
                owner_user_id,
                application_id,
            )
        except Exception as exc:
            if getattr(exc, "code", None) == "application_workspace_not_found":
                return None
            raise
        return NetworkingApplicationReference(
            application_id=source.application_id,
            stage=source.stage.value,
        )
