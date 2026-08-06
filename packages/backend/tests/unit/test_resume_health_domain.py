"""Domain state and guest capability invariants."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from rezumi.modules.resume_health.domain import (
    JobKind,
    JobStatus,
    OwnerScope,
    ProcessingJob,
    ProcessingStage,
)
from rezumi.modules.resume_health.domain.errors import ResumeStateConflict
from rezumi.modules.resume_health.infrastructure.security import HmacGuestCapabilityManager


def test_owner_scope_requires_exactly_one_owner() -> None:
    with pytest.raises(ValueError):
        OwnerScope()
    with pytest.raises(ValueError):
        OwnerScope(user_id=uuid4(), guest_session_id=uuid4())


def test_guest_capability_is_high_entropy_hashed_and_constant_time_verified() -> None:
    manager = HmacGuestCapabilityManager("a" * 32)
    issued = manager.issue()
    parsed = manager.parse(issued.encoded)

    assert parsed is not None
    identifier, secret = parsed
    assert identifier == issued.id
    assert secret.encode() not in issued.digest
    assert manager.verify(issued.digest, secret)
    assert not manager.verify(issued.digest, secret + "wrong")
    assert manager.parse("not-a-capability") is None


def test_processing_job_enforces_transitions_progress_and_dead_letter() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    job = ProcessingJob(
        id=uuid4(),
        document_id=uuid4(),
        owner=OwnerScope(user_id=uuid4()),
        kind=JobKind.PARSE,
        idempotency_key="test-key",
        request_hash=b"x" * 32,
        trace_id="trace",
        status=JobStatus.QUEUED,
        stage=ProcessingStage.QUEUED,
        progress=None,
        attempts=0,
        max_attempts=3,
        created_at=now,
        updated_at=now,
    )

    job.start(now)
    job.advance(ProcessingStage.EXTRACTION, 50, now)
    assert job.status == JobStatus.RUNNING
    assert job.attempts == 1
    assert job.progress == 50

    with pytest.raises(ValueError):
        job.advance(ProcessingStage.EXTRACTION, 101, now)

    job.fail("provider_failed", retryable=True, now=now, exhausted=True)
    assert job.status == JobStatus.DEAD_LETTERED
    assert not job.retryable
    assert job.dead_lettered_at == now

    with pytest.raises(ResumeStateConflict):
        job.advance(ProcessingStage.ANALYSIS, 80, now)
