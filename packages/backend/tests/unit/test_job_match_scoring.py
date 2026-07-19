"""Deterministic Job Match scoring tests."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from careeros.modules.job_match.domain import (
    EmploymentType,
    JobPosting,
    JobSourceKind,
    RequirementMatchState,
    WorkModel,
)
from careeros.modules.job_match.domain.scoring import (
    extract_job_content,
    score_job_match,
)
from job_match_memory import sample_job_text, sample_snapshot


def _job(source_text: str) -> JobPosting:
    return JobPosting(
        id=uuid4(),
        owner_user_id=uuid4(),
        title="Product Manager",
        company="Example Co",
        location="Remote",
        work_model=WorkModel.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        compensation=None,
        application_deadline=None,
        source_kind=JobSourceKind.PASTE,
        source_url=None,
        source_text=source_text,
        source_sha256=sha256(source_text.encode("utf-8")).digest(),
        idempotency_key="job-create-test-key",
        idempotency_fingerprint="sha256:test",
        target_role_id=None,
        target_role_title=None,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_extract_job_content_preserves_source_spans_and_metadata() -> None:
    content = extract_job_content(sample_job_text())

    assert content.title == "Product Manager"
    assert content.company == "Example Co"
    assert len(content.requirements) == 3
    first = content.requirements[0]
    assert first.text.startswith("Must have experience")
    assert (
        sample_job_text()[first.source_start : first.source_end]
        .strip()
        .endswith("customer discovery.")
    )


def test_score_job_match_links_only_eligible_snapshot_evidence() -> None:
    content = extract_job_content(sample_job_text())
    requirement_ids = tuple((uuid4(), requirement) for requirement in content.requirements)

    score = score_job_match(_job(sample_job_text()), requirement_ids, sample_snapshot())

    assert score.display_score is not None
    assert score.hard_gap_count >= 0
    assert any(
        match.state is RequirementMatchState.STRONG and match.evidence
        for match in score.requirement_matches
    )
    assert score.input_snapshot["engine"] == score.engine_version
