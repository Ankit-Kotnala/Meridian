"""Application-level Change Studio tests using deterministic inward ports."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from careeros.modules.change_studio.application import (
    ChangeStudioService,
    CreateChangeSet,
    EditOperation,
    RequestContext,
)
from careeros.modules.change_studio.domain import (
    ChangeOperationType,
    ChangeStudioIdempotencyConflict,
    ChangeStudioNotFound,
    ChangeStudioVersionConflict,
    ChangeTargetKind,
    ClaimKind,
    GroundingFailed,
    GroundingStatus,
    ProviderClaimCandidate,
    ProviderOperationCandidate,
    ProviderOutputRejected,
    RiskLevel,
    ground_operation,
)
from careeros.modules.change_studio.infrastructure import DeterministicSuggestionProvider
from change_studio_memory import (
    ANALYSIS_ID,
    EVIDENCE_ID,
    METRIC_EVIDENCE_ID,
    MISSING_REQUIREMENT_ID,
    OWNER_ID,
    REQUIREMENT_ID,
    FixedClock,
    MemoryChangeStudio,
    StaticEvidenceProvider,
    StaticJobAnalysisProvider,
    UuidFactory,
    sample_evidence,
)


def _context(owner=OWNER_ID) -> RequestContext:
    return RequestContext(owner, f"change-studio-{owner.hex[:8]}", "6" * 32)


def _service(
    memory: MemoryChangeStudio,
    *,
    provider=None,
    evidence: StaticEvidenceProvider | None = None,
) -> ChangeStudioService:
    return ChangeStudioService(
        unit_of_work=memory,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        provider=provider or DeterministicSuggestionProvider(),
        evidence=evidence or StaticEvidenceProvider(),
        job_matches=StaticJobAnalysisProvider(),
    )


@pytest.mark.asyncio
async def test_create_change_set_generates_grounded_operations_and_questions() -> None:
    memory = MemoryChangeStudio()
    service = _service(memory)
    other = uuid4()

    with pytest.raises(ChangeStudioNotFound):
        await service.create_change_set(
            OWNER_ID,
            CreateChangeSet(analysis_id=ANALYSIS_ID),
            "change-create-cross-user",
            _context(other),
        )

    created = await service.create_change_set(
        OWNER_ID,
        CreateChangeSet(analysis_id=ANALYSIS_ID),
        "change-create-key",
        _context(),
    )
    repeated = await service.create_change_set(
        OWNER_ID,
        CreateChangeSet(analysis_id=ANALYSIS_ID),
        "change-create-key",
        _context(),
    )

    assert repeated.change_set.id == created.change_set.id
    assert created.change_set.owner_user_id == OWNER_ID
    assert created.operations[0].grounding_status is GroundingStatus.GROUNDED
    assert created.operations[0].requires_confirmation is True
    assert created.claims[0].evidence_id == EVIDENCE_ID
    assert created.questions[0].requirement_id == MISSING_REQUIREMENT_ID
    assert created.provider_runs[0].input_evidence_ids == (EVIDENCE_ID,)
    assert memory.audits[-1].target_id == created.change_set.id


@pytest.mark.asyncio
async def test_accepting_operation_creates_immutable_versions_and_allows_undo_redo() -> None:
    memory = MemoryChangeStudio()
    service = _service(memory)
    created = await service.create_change_set(
        OWNER_ID,
        CreateChangeSet(analysis_id=ANALYSIS_ID),
        "change-accept-create",
        _context(),
    )
    operation = created.operations[0]

    accepted = await service.accept_operation(
        OWNER_ID,
        created.change_set.id,
        operation.id,
        created.change_set.version,
        "change-accept-key",
        _context(),
    )
    assert accepted.change_set.version == 2
    assert len(accepted.versions) == 2
    assert accepted.versions[-1].parent_version_id == created.versions[0].id
    assert operation.after_text in accepted.versions[-1].content

    undone = await service.undo(
        OWNER_ID,
        created.change_set.id,
        accepted.change_set.version,
        "change-undo-key",
        _context(),
    )
    assert undone.change_set.current_version_id == created.versions[0].id

    redone = await service.redo(
        OWNER_ID,
        created.change_set.id,
        undone.change_set.version,
        "change-redo-key",
        _context(),
    )
    assert redone.change_set.current_version_id == accepted.versions[-1].id

    restored = await service.restore_version(
        OWNER_ID,
        created.change_set.id,
        created.versions[0].id,
        redone.change_set.version,
        "change-restore-key",
        _context(),
    )
    assert restored.change_set.current_version_id == created.versions[0].id


@pytest.mark.asyncio
async def test_ungrounded_user_edit_is_rejected() -> None:
    memory = MemoryChangeStudio()
    service = _service(memory)
    created = await service.create_change_set(
        OWNER_ID,
        CreateChangeSet(analysis_id=ANALYSIS_ID),
        "change-edit-create",
        _context(),
    )

    with pytest.raises(GroundingFailed):
        await service.edit_operation(
            OWNER_ID,
            created.change_set.id,
            created.operations[0].id,
            created.change_set.version,
            EditOperation(after_text="Invented a new ownership claim about billing."),
            "change-edit-key",
            _context(),
        )


@pytest.mark.asyncio
async def test_version_and_idempotency_conflicts_are_enforced() -> None:
    memory = MemoryChangeStudio()
    service = _service(memory)
    created = await service.create_change_set(
        OWNER_ID,
        CreateChangeSet(analysis_id=ANALYSIS_ID),
        "change-conflict-create",
        _context(),
    )

    with pytest.raises(ChangeStudioVersionConflict):
        await service.accept_operation(
            OWNER_ID,
            created.change_set.id,
            created.operations[0].id,
            99,
            "change-wrong-version",
            _context(),
        )

    with pytest.raises(ChangeStudioIdempotencyConflict):
        await service.create_change_set(
            OWNER_ID,
            CreateChangeSet(
                analysis_id=ANALYSIS_ID,
                target_kind=ChangeTargetKind.PROFILE_SUMMARY,
            ),
            "change-conflict-create",
            _context(),
        )


@pytest.mark.asyncio
async def test_provider_output_rejection_and_blocked_unsupported_claims() -> None:
    memory = MemoryChangeStudio()

    class MalformedProvider:
        async def generate(self, request):
            del request
            return _provider_response({"operations": [{"after": "missing fields"}]})

    with pytest.raises(ProviderOutputRejected):
        await _service(memory, provider=MalformedProvider()).create_change_set(
            OWNER_ID,
            CreateChangeSet(analysis_id=ANALYSIS_ID),
            "change-malformed-provider",
            _context(),
        )

    class UnsupportedProvider:
        async def generate(self, request):
            return _provider_response(
                {
                    "operations": [
                        {
                            "operationType": "add_bullet",
                            "targetId": str(REQUIREMENT_ID),
                            "targetKind": request.target_kind.value,
                            "before": "",
                            "after": "Owned billing platform migrations.",
                            "reason": "Should be blocked because evidence does not say this.",
                            "claims": [
                                {
                                    "text": "Owned billing platform migrations.",
                                    "kind": "responsibility",
                                    "evidenceIds": [str(EVIDENCE_ID)],
                                }
                            ],
                            "requirementIds": [str(REQUIREMENT_ID)],
                            "confidenceBasisPoints": 8000,
                            "risk": "high",
                            "requiresConfirmation": True,
                            "expectedScoreDeltaBasisPoints": None,
                        }
                    ],
                    "questions": [],
                }
            )

    blocked = await _service(
        MemoryChangeStudio(),
        provider=UnsupportedProvider(),
    ).create_change_set(
        OWNER_ID,
        CreateChangeSet(analysis_id=ANALYSIS_ID),
        "change-unsupported-provider",
        _context(),
    )
    assert blocked.operations[0].grounding_status is GroundingStatus.BLOCKED
    assert "unsupported_claim" in blocked.operations[0].grounding_codes
    assert "contribution_elevation" in blocked.operations[0].grounding_codes


def test_numeric_claims_require_confirmed_metric_evidence() -> None:
    unsupported, metric = sample_evidence()
    candidate = ProviderOperationCandidate(
        operation_type=ChangeOperationType.ADD_BULLET,
        target_id=REQUIREMENT_ID,
        target_kind=ChangeTargetKind.TAILORED_RESUME_BULLET,
        before="",
        after="Improved activation by 40%.",
        reason="Uses confirmed metric evidence.",
        claims=(
            ProviderClaimCandidate(
                text="Improved activation by 40%.",
                kind=ClaimKind.METRIC_OUTCOME,
                evidence_ids=(METRIC_EVIDENCE_ID,),
            ),
        ),
        requirement_ids=(REQUIREMENT_ID,),
        confidence_basis_points=9000,
        risk=RiskLevel.MEDIUM,
        requires_confirmation=True,
        expected_score_delta_basis_points=None,
    )
    requirements = {
        REQUIREMENT_ID: sample_requirements()[REQUIREMENT_ID],
    }

    failed = ground_operation(
        candidate,
        evidence={METRIC_EVIDENCE_ID: replace_strength(metric, "supported")},
        requirements=requirements,
    )
    passed = ground_operation(
        candidate,
        evidence={METRIC_EVIDENCE_ID: metric},
        requirements=requirements,
    )

    assert "numeric_not_grounded" in failed.codes
    assert passed.status is GroundingStatus.GROUNDED
    assert unsupported.id == EVIDENCE_ID


def sample_requirements() -> dict[UUID, object]:
    from change_studio_memory import sample_analysis

    return {item.requirement.id: item.requirement for item in sample_analysis().requirements}


def replace_strength(
    evidence,
    strength: str,
):
    from dataclasses import replace

    return replace(evidence, strength=strength)


def _provider_response(payload: dict[str, object]):
    from careeros.modules.change_studio.application import AiProviderResponse

    return AiProviderResponse(
        provider_name="test-provider",
        provider_model="test-model",
        latency_ms=0,
        payload=payload,
    )
