"""Application-boundary adapter from Role Explorer to Job Match."""

from __future__ import annotations

from uuid import UUID

from rezumi.modules.role_readiness.application import RoleReadinessService


class RoleReadinessRoleContextProvider:
    """Resolve optional target role context through the Role Readiness service."""

    def __init__(self, service: RoleReadinessService) -> None:
        self._service = service

    async def role_title(self, owner_user_id: UUID, role_id: UUID) -> str:
        _ = owner_user_id
        return (await self._service.get_role(role_id)).role.title
