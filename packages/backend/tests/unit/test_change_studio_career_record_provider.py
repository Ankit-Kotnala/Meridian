"""Performance and provenance tests for the Change Studio Career Record adapter."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from uuid import UUID

import pytest

from careeros.modules.change_studio.infrastructure.career_record_provider import (
    CareerRecordChangeStudioEvidenceProvider,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000008101")
EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000008102")
REVISION_ID = UUID("00000000-0000-4000-8000-000000008103")


class _BatchCareerRecord:
    def __init__(self) -> None:
        self.batch_calls = 0
        self.single_calls = 0

    async def get_evidence_batch_with_eligibility(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[tuple[SimpleNamespace, SimpleNamespace], ...]:
        assert owner_user_id == OWNER_ID
        assert evidence_ids == (EVIDENCE_ID,)
        self.batch_calls += 1
        statement = "Reduced release validation time by 40%."
        return (
            (
                SimpleNamespace(
                    item=SimpleNamespace(id=EVIDENCE_ID),
                    revision=SimpleNamespace(
                        id=REVISION_ID,
                        revision=3,
                        title="Release validation",
                        statement=statement,
                        context="Platform engineering",
                        strength=SimpleNamespace(value="confirmed"),
                    ),
                    metrics=(),
                ),
                SimpleNamespace(eligible=True),
            ),
        )

    async def get_evidence_with_eligibility(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
    ) -> tuple[SimpleNamespace, SimpleNamespace]:
        self.single_calls += 1
        raise AssertionError("the normal path must not issue per-evidence reads")


@pytest.mark.asyncio
async def test_evidence_contexts_use_one_bounded_batch_and_keep_exact_revision() -> None:
    service = _BatchCareerRecord()
    provider = CareerRecordChangeStudioEvidenceProvider(service)  # type: ignore[arg-type]

    contexts = await provider.evidence_contexts(
        OWNER_ID,
        (EVIDENCE_ID, EVIDENCE_ID),
    )

    assert service.batch_calls == 1
    assert service.single_calls == 0
    assert len(contexts) == 1
    assert contexts[0].evidence_revision_id == REVISION_ID
    assert contexts[0].revision_number == 3
    assert (
        contexts[0].statement_sha256
        == hashlib.sha256(contexts[0].statement.encode("utf-8")).hexdigest()
    )
