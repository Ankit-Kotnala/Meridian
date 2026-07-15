"""Compatibility bridge coverage for workflow-backed core attachment status."""

from pathlib import Path
from uuid import UUID

import pytest

from career_record_attachment_memory import (
    FakeAttachmentStorage,
    FakeClock,
    FakeExtractor,
    FakeScanner,
    InMemoryAttachmentUnitOfWorkFactory,
    SequentialIds,
    SequentialTokens,
)
from careeros.modules.career_record.application.attachment_workflow import (
    AttachmentLimits,
    AttachmentProcessor,
    AttachmentWorkflowService,
)
from careeros.modules.career_record.application.models import AttachmentAdmissionRequest
from careeros.modules.career_record.domain import AttachmentStatus
from careeros.modules.career_record.infrastructure.attachment_admission import (
    AttachmentAdmissionBridge,
)

OWNER = UUID(int=41)
EVIDENCE = UUID(int=42)
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"


@pytest.mark.asyncio
async def test_bridge_preserves_owner_scope_and_reflects_live_processing_status(
    tmp_path: Path,
) -> None:
    factory = InMemoryAttachmentUnitOfWorkFactory()
    factory.add_evidence(OWNER, EVIDENCE)
    clock = FakeClock()
    ids = SequentialIds()
    storage = FakeAttachmentStorage()
    limits = AttachmentLimits(temp_root=tmp_path.resolve())
    workflow = AttachmentWorkflowService(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        limits=limits,
        ids=ids,
        tokens=SequentialTokens(),
    )
    bridge = AttachmentAdmissionBridge(workflow)

    admission = await bridge.request_upload(
        OWNER,
        AttachmentAdmissionRequest(
            evidence_id=EVIDENCE,
            display_filename="support.pdf",
            media_type="application/pdf",
            expected_size=len(PDF),
        ),
    )
    assert admission.status is AttachmentStatus.PENDING
    storage.upload_latest(PDF)
    finalized = await bridge.finalize(OWNER, admission.attachment_id)
    assert finalized.status is AttachmentStatus.QUARANTINED

    job_id = next(iter(factory.state.jobs))
    processor = AttachmentProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        scanner=FakeScanner(),
        extractor=FakeExtractor(),
        limits=limits,
        ids=ids,
    )
    await processor.process_job(job_id, "bridge-processing-token")

    assert await bridge.status(OWNER, admission.attachment_id) is AttachmentStatus.CLEAN

    await bridge.delete(OWNER, admission.attachment_id)
    assert factory.state.attachments[admission.attachment_id].status.value == "deleting"
