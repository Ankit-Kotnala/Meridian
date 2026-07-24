"""Source-adapter tests for exact Phase 8 snapshot pinning."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec
from uuid import UUID

import pytest

from careeros.modules.application_workspace.application import (
    ApplicationSourceEvidenceReference,
)
from careeros.modules.application_workspace.domain import ApplicationWorkspaceConflict
from careeros.modules.application_workspace.infrastructure import (
    CareerRecordApplicationEvidenceSnapshotProvider,
    JobMatchApplicationSnapshotProvider,
    ResumeBuilderVersionSnapshotProvider,
)
from careeros.modules.career_record.application import CareerRecordService
from careeros.modules.job_match.application import JobMatchService

_OWNER_ID = UUID("00000000-0000-4000-8000-000000001001")
_JOB_ID = UUID("00000000-0000-4000-8000-000000001002")
_ANALYSIS_ID = UUID("00000000-0000-4000-8000-000000001003")
_REQUIREMENT_ID = UUID("00000000-0000-4000-8000-000000001004")
_EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000001005")
_REVISION_ID = UUID("00000000-0000-4000-8000-000000001006")
_MATCH_ID = UUID("00000000-0000-4000-8000-000000001007")
_CURRENT_REVISION_ID = UUID("00000000-0000-4000-8000-000000001008")
_RESUME_VERSION_ID = UUID("00000000-0000-4000-8000-000000001009")


@pytest.mark.asyncio
async def test_job_snapshot_pins_only_analysis_for_exact_current_job_version() -> None:
    service = create_autospec(JobMatchService, instance=True)
    job = SimpleNamespace(
        id=_JOB_ID,
        version=4,
        title="Principal Product Engineer",
        company="Example Co",
        location="Remote",
        application_deadline=None,
        source_sha256=bytes.fromhex("a" * 64),
        source_kind=SimpleNamespace(value="manual"),
    )
    requirement = SimpleNamespace(
        id=_REQUIREMENT_ID,
        requirement_type=SimpleNamespace(value="responsibility"),
        importance=SimpleNamespace(value="mandatory"),
        text="Lead product delivery.",
        source_start=0,
        source_end=22,
    )
    service.get_job.return_value = SimpleNamespace(
        job=job,
        requirements=(requirement,),
    )
    service.get_latest_analysis_for_job.return_value = SimpleNamespace(
        analysis=SimpleNamespace(
            id=_ANALYSIS_ID,
            input_snapshot={
                "job": {
                    "version": 4,
                    "sourceSha256": "a" * 64,
                }
            },
        ),
        requirement_matches=(SimpleNamespace(id=_MATCH_ID, requirement_id=_REQUIREMENT_ID),),
        evidence_links=(
            SimpleNamespace(
                requirement_match_id=_MATCH_ID,
                evidence_id=_EVIDENCE_ID,
            ),
        ),
    )
    provider = JobMatchApplicationSnapshotProvider(service)

    snapshot = await provider.snapshot(_OWNER_ID, _JOB_ID)
    assert snapshot.latest_analysis_id == _ANALYSIS_ID
    assert snapshot.requirement_support[0].requirement_id == _REQUIREMENT_ID
    assert snapshot.requirement_support[0].evidence_id == _EVIDENCE_ID

    service.get_latest_analysis_for_job.return_value.analysis.input_snapshot = {
        "job": {
            "version": 3,
            "sourceSha256": "b" * 64,
        }
    }
    stale = await provider.snapshot(_OWNER_ID, _JOB_ID)
    assert stale.latest_analysis_id is None


@pytest.mark.asyncio
async def test_evidence_snapshot_uses_one_bounded_bulk_application_query() -> None:
    service = create_autospec(CareerRecordService, instance=True)
    statement = "Led product delivery."
    revision = SimpleNamespace(
        id=_REVISION_ID,
        evidence_id=_EVIDENCE_ID,
        revision=3,
        statement=statement,
        strength=SimpleNamespace(value="confirmed"),
        has_numeric_claim=False,
    )
    current_statement = "A later unrelated evidence statement."
    current_revision = SimpleNamespace(
        id=_CURRENT_REVISION_ID,
        evidence_id=_EVIDENCE_ID,
        revision=4,
        statement=current_statement,
        strength=SimpleNamespace(value="confirmed"),
        has_numeric_claim=False,
    )
    record = SimpleNamespace(
        item=SimpleNamespace(id=_EVIDENCE_ID),
        revision=current_revision,
        revisions=(revision, current_revision),
    )
    decision = SimpleNamespace(eligible=True)
    service.get_evidence_batch_with_eligibility.return_value = ((record, decision),)
    provider = CareerRecordApplicationEvidenceSnapshotProvider(service)
    reference = ApplicationSourceEvidenceReference(
        evidence_id=_EVIDENCE_ID,
        evidence_revision_id=_REVISION_ID,
        revision_number=3,
        statement_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        claim_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        link_basis="evidence_statement",
        source_skill_id=None,
    )

    pins = await provider.snapshot(
        _OWNER_ID,
        (reference, reference),
    )

    service.get_evidence_batch_with_eligibility.assert_awaited_once_with(
        _OWNER_ID,
        (_EVIDENCE_ID,),
    )
    assert len(pins) == 1
    assert pins[0].evidence_revision_id == _REVISION_ID
    assert pins[0].statement == statement
    assert pins[0].statement_sha256 == hashlib.sha256(statement.encode()).hexdigest()


@pytest.mark.asyncio
async def test_resume_snapshot_refuses_legacy_bullets_without_exact_revision_pins() -> None:
    service = SimpleNamespace(
        get_version=AsyncMock(
            return_value=SimpleNamespace(
                sections=(
                    SimpleNamespace(
                        items=(
                            SimpleNamespace(
                                id=UUID("00000000-0000-4000-8000-00000000100a"),
                                text="A legacy claim with only an evidence item identifier.",
                                evidence_ids=(_EVIDENCE_ID,),
                                evidence_references=(),
                            ),
                        )
                    ),
                ),
            )
        )
    )
    provider = ResumeBuilderVersionSnapshotProvider(service)  # type: ignore[arg-type]

    with pytest.raises(
        ApplicationWorkspaceConflict,
        match="provenance ledger is incomplete or invalid",
    ):
        await provider.snapshot(_OWNER_ID, _RESUME_VERSION_ID)
