"""Adapter that reads competency gaps from Role Readiness analyses.

Only the application-layer `RoleReadinessService` is imported here, never
`role_readiness.domain` internals. Match states are compared as their wire
values so this adapter stays on the explicit application contract.
"""

from __future__ import annotations

from uuid import UUID

from rezumi.modules.career_growth.application.ports import GapSnapshot
from rezumi.modules.role_readiness.application import RoleReadinessService


class RoleReadinessGapProvider:
    def __init__(self, service: RoleReadinessService) -> None:
        self._service = service

    async def list_gaps(
        self,
        owner_user_id: UUID,
        role_profile_id: UUID | None = None,
    ) -> tuple[GapSnapshot, ...]:
        records = await self._service.list_history(
            owner_user_id,
            role_id=role_profile_id,
            limit=1,
        )
        if not records.data:
            return ()
        latest = records.data[0]
        gaps: list[GapSnapshot] = []
        for result in latest.competency_results:
            if result.gap_kind is None:
                continue
            if result.match_state not in {"missing", "unknown"}:
                continue
            gaps.append(
                GapSnapshot(
                    gap_kind=result.gap_kind,
                    label=result.label,
                    requirement_text=result.explanation,
                    role_profile_id=latest.analysis.role_id,
                )
            )
        return tuple(gaps)
