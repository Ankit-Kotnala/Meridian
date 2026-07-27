"""Revision-level provenance regressions for Resume Builder source adapters."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from careeros.modules.change_studio.domain import (
    ChangeClaim,
    ClaimKind,
    ValidationStatus,
)
from careeros.modules.resume_builder.domain import ResumeEvidenceLinkBasis
from careeros.modules.resume_builder.infrastructure.sources import (
    CareerRecordResumeSourceProvider,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000007001")
EVIDENCE_ONE = UUID("00000000-0000-4000-8000-000000007002")
EVIDENCE_TWO = UUID("00000000-0000-4000-8000-000000007003")
OLD_REVISION = UUID("00000000-0000-4000-8000-000000007004")
CURRENT_REVISION = UUID("00000000-0000-4000-8000-000000007005")
SECOND_REVISION = UUID("00000000-0000-4000-8000-000000007006")
CHANGE_SET_ID = UUID("00000000-0000-4000-8000-000000007007")
VERSION_ID = UUID("00000000-0000-4000-8000-000000007008")
OPERATION_ONE = UUID("00000000-0000-4000-8000-000000007009")
OPERATION_TWO = UUID("00000000-0000-4000-8000-00000000700a")
UNLINKED_SKILL = UUID("00000000-0000-4000-8000-00000000700b")


@pytest.mark.asyncio
async def test_change_studio_claims_keep_exact_per_line_historical_revisions() -> None:
    old_statement = "Designed the original customer discovery program."
    current_statement = "Unrelated current evidence after an edit."
    second_statement = "Built the launch measurement plan."
    first_claim = "Designed the original customer discovery program."
    second_claim = "Built the launch measurement plan."
    now = datetime(2026, 7, 25, 12, tzinfo=UTC)

    readiness = SimpleNamespace(
        entities=(),
        evidence=(
            SimpleNamespace(
                id=EVIDENCE_ONE,
                evidence_revision_id=CURRENT_REVISION,
                revision_number=2,
                statement_sha256=_sha(current_statement),
                statement=current_statement,
                entity_ids=(),
                skill_ids=(),
            ),
            SimpleNamespace(
                id=EVIDENCE_TWO,
                evidence_revision_id=SECOND_REVISION,
                revision_number=1,
                statement_sha256=_sha(second_statement),
                statement=second_statement,
                entity_ids=(),
                skill_ids=(),
            ),
        ),
        personal_facts=(),
        skills=(
            SimpleNamespace(
                id=UNLINKED_SKILL,
                name="Unrelated skill",
            ),
        ),
    )
    old_revision = SimpleNamespace(
        id=OLD_REVISION,
        revision=1,
        statement=old_statement,
    )
    current_revision = SimpleNamespace(
        id=CURRENT_REVISION,
        revision=2,
        statement=current_statement,
    )
    second_revision = SimpleNamespace(
        id=SECOND_REVISION,
        revision=1,
        statement=second_statement,
    )
    career_record = SimpleNamespace(
        get_profile=AsyncMock(
            return_value=SimpleNamespace(
                profile=SimpleNamespace(
                    professional_headline="Product leader",
                    summary="Unrelated profile summary must never inherit evidence.",
                )
            )
        ),
        readiness_snapshot=AsyncMock(return_value=readiness),
        get_evidence_batch_with_eligibility=AsyncMock(
            return_value=(
                (
                    SimpleNamespace(
                        item=SimpleNamespace(id=EVIDENCE_ONE),
                        revisions=(old_revision, current_revision),
                    ),
                    SimpleNamespace(eligible=True),
                ),
                (
                    SimpleNamespace(
                        item=SimpleNamespace(id=EVIDENCE_TWO),
                        revisions=(second_revision,),
                    ),
                    SimpleNamespace(eligible=True),
                ),
            )
        ),
    )
    claims = (
        _claim(
            UUID("00000000-0000-4000-8000-00000000700c"),
            OPERATION_ONE,
            first_claim,
            EVIDENCE_ONE,
            OLD_REVISION,
            1,
            old_statement,
            now,
        ),
        _claim(
            UUID("00000000-0000-4000-8000-00000000700d"),
            OPERATION_TWO,
            second_claim,
            EVIDENCE_TWO,
            SECOND_REVISION,
            1,
            second_statement,
            now,
        ),
    )
    change_studio = SimpleNamespace(
        get_change_set=AsyncMock(
            return_value=SimpleNamespace(
                change_set=SimpleNamespace(current_version_id=VERSION_ID),
                versions=(
                    SimpleNamespace(
                        id=VERSION_ID,
                        operation_ids=(OPERATION_ONE, OPERATION_TWO),
                    ),
                ),
                operations=(
                    SimpleNamespace(id=OPERATION_ONE, after_text=first_claim),
                    SimpleNamespace(id=OPERATION_TWO, after_text=second_claim),
                ),
                claims=claims,
            )
        )
    )
    provider = CareerRecordResumeSourceProvider(
        career_record,
        change_studio=change_studio,
    )

    snapshot = await provider.snapshot(
        OWNER_ID,
        change_set_id=CHANGE_SET_ID,
        change_set_version_id=VERSION_ID,
    )

    change_bullets = tuple(
        bullet for bullet in snapshot.bullets if bullet.source == "change_studio"
    )
    assert tuple(bullet.text for bullet in change_bullets) == (
        first_claim,
        second_claim,
    )
    assert tuple(bullet.evidence_ids for bullet in change_bullets) == (
        (EVIDENCE_ONE,),
        (EVIDENCE_TWO,),
    )
    assert change_bullets[0].evidence_references[0].evidence_revision_id == OLD_REVISION
    assert (
        change_bullets[0].evidence_references[0].link_basis
        is ResumeEvidenceLinkBasis.CHANGE_STUDIO_CLAIM
    )
    assert not any(
        bullet.text == current_statement and bullet.evidence_ids == (EVIDENCE_ONE,)
        for bullet in snapshot.bullets
    )
    assert snapshot.summary is None
    assert snapshot.skills == ()
    assert all(bullet.text != "Unrelated skill" for bullet in snapshot.bullets)


def _claim(
    claim_id: UUID,
    operation_id: UUID,
    text: str,
    evidence_id: UUID,
    revision_id: UUID,
    revision_number: int,
    statement: str,
    now: datetime,
) -> ChangeClaim:
    return ChangeClaim(
        id=claim_id,
        owner_user_id=OWNER_ID,
        change_set_id=CHANGE_SET_ID,
        operation_id=operation_id,
        claim_kind=ClaimKind.ACHIEVEMENT,
        text=text,
        evidence_id=evidence_id,
        evidence_revision_id=revision_id,
        evidence_revision_number=revision_number,
        evidence_statement_sha256=_sha(statement),
        evidence_title="Pinned evidence",
        evidence_strength="confirmed",
        source_excerpt=statement,
        validation_status=ValidationStatus.PASSED,
        validation_codes=("grounded",),
        sort_order=10,
        created_at=now,
    )


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
