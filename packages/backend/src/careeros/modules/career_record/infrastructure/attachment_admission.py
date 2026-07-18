"""Compatibility bridge from the Career Record port to the private workflow."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from careeros.modules.career_record.application.attachment_workflow import (
    AdmitAttachment,
    AttachmentRequestContext,
    AttachmentWorkflowService,
)
from careeros.modules.career_record.application.attachment_workflow import (
    AttachmentStatus as WorkflowAttachmentStatus,
)
from careeros.modules.career_record.application.models import (
    AttachmentAdmissionRequest,
    AttachmentAdmissionResult,
    AttachmentFinalization,
)
from careeros.modules.career_record.domain import AttachmentStatus

AttachmentContextFactory = Callable[[UUID], AttachmentRequestContext]


class AttachmentAdmissionBridge:
    """Keep the core status/query port backed by the authoritative workflow.

    HTTP upload and finalization endpoints use ``AttachmentWorkflowService``
    directly because the older core port cannot represent required signed-upload
    headers or caller-supplied idempotency keys. This bridge remains useful for
    core evidence eligibility checks and cascading owner deletions.
    """

    def __init__(
        self,
        workflow: AttachmentWorkflowService,
        context_factory: AttachmentContextFactory | None = None,
    ) -> None:
        self._workflow = workflow
        self._context_factory = context_factory or _system_context

    async def request_upload(
        self, owner_user_id: UUID, command: AttachmentAdmissionRequest
    ) -> AttachmentAdmissionResult:
        admitted = await self._workflow.admit(
            owner_user_id,
            AdmitAttachment(
                evidence_id=command.evidence_id,
                display_filename=command.display_filename,
                media_type=command.media_type,
                expected_size=command.expected_size,
            ),
            self._context_factory(owner_user_id),
        )
        return AttachmentAdmissionResult(
            attachment_id=admitted.attachment_id,
            status=AttachmentStatus.PENDING,
            expires_at=admitted.expires_at,
            upload_url=admitted.upload.url,
        )

    async def status(self, owner_user_id: UUID, attachment_id: UUID) -> AttachmentStatus:
        view = await self._workflow.get(
            owner_user_id, attachment_id, self._context_factory(owner_user_id)
        )
        return _core_status(view.status)

    async def finalize(self, owner_user_id: UUID, attachment_id: UUID) -> AttachmentFinalization:
        context = self._context_factory(owner_user_id)
        await self._workflow.finalize(
            owner_user_id,
            attachment_id,
            f"core-attachment-finalize-{attachment_id}",
            context,
        )
        view = await self._workflow.get(owner_user_id, attachment_id, context)
        if view.expected_size is None:
            raise RuntimeError("finalized attachment size is unavailable")
        return AttachmentFinalization(
            attachment_id=view.attachment_id,
            status=_core_status(view.status),
            size_bytes=view.expected_size,
            content_sha256=view.content_sha256,
        )

    async def delete(self, owner_user_id: UUID, attachment_id: UUID) -> None:
        await self._workflow.delete(
            owner_user_id, attachment_id, self._context_factory(owner_user_id)
        )


def _system_context(owner_user_id: UUID) -> AttachmentRequestContext:
    nonce = uuid4().hex
    return AttachmentRequestContext(
        actor_user_id=owner_user_id,
        request_id=f"career-record-bridge-{nonce}",
        trace_id=nonce,
    )


def _core_status(status: WorkflowAttachmentStatus) -> AttachmentStatus:
    if status is WorkflowAttachmentStatus.ADMITTED:
        return AttachmentStatus.PENDING
    if status is WorkflowAttachmentStatus.PROCESSING:
        return AttachmentStatus.QUARANTINED
    return AttachmentStatus(status.value)
