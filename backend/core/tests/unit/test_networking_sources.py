"""Purpose-minimized Networking source-boundary tests."""

from __future__ import annotations

from dataclasses import fields
from uuid import UUID

import pytest

from rezumi.modules.application_workspace.application import ApplicationReference
from rezumi.modules.application_workspace.domain import ApplicationStage
from rezumi.modules.networking.application import NetworkingApplicationReference
from rezumi.modules.networking.infrastructure import (
    ApplicationWorkspaceNetworkingReferenceProvider,
)

_OWNER_ID = UUID("00000000-0000-4000-8000-000000009201")
_APPLICATION_ID = UUID("00000000-0000-4000-8000-000000009202")


class _NarrowApplicationService:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_application_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationReference:
        self.calls.append((owner_user_id, application_id))
        return ApplicationReference(
            application_id=application_id,
            stage=ApplicationStage.INTERVIEW,
        )


class _MissingApplicationService:
    async def get_application_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationReference:
        _ = owner_user_id, application_id
        error = LookupError("owner-scoped application was not found")
        error.code = "application_workspace_not_found"  # type: ignore[attr-defined]
        raise error


@pytest.mark.asyncio
async def test_networking_requests_only_content_free_application_reference() -> None:
    service = _NarrowApplicationService()
    provider = ApplicationWorkspaceNetworkingReferenceProvider(service)

    reference = await provider.get_reference(_OWNER_ID, _APPLICATION_ID)

    assert service.calls == [(_OWNER_ID, _APPLICATION_ID)]
    assert not hasattr(service, "get_interview_context")
    assert tuple(field.name for field in fields(ApplicationReference)) == (
        "application_id",
        "stage",
    )
    assert reference == NetworkingApplicationReference(
        application_id=_APPLICATION_ID,
        stage=ApplicationStage.INTERVIEW.value,
    )


@pytest.mark.asyncio
async def test_networking_hides_owner_scoped_application_misses() -> None:
    provider = ApplicationWorkspaceNetworkingReferenceProvider(_MissingApplicationService())

    assert await provider.get_reference(_OWNER_ID, _APPLICATION_ID) is None
