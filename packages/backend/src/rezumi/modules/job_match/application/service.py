"""Job Match application service and deterministic orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rezumi.modules.job_match.domain import (
    EmploymentType,
    JobAuditAction,
    JobMatchAnalysis,
    JobMatchAuditEvent,
    JobMatchComponent,
    JobMatchConflict,
    JobMatchIdempotencyConflict,
    JobMatchNotFound,
    JobMatchValidationError,
    JobMatchVersionConflict,
    JobPosting,
    JobRequirement,
    JobSourceKind,
    OpportunityPriorityAnalysis,
    OpportunityPriorityInput,
    RequirementEvidenceLink,
    RequirementMatch,
    WorkModel,
    extract_job_content,
    score_job_match,
    score_opportunity_priority,
)
from rezumi.modules.job_match.domain.scoring import (
    ExtractedRequirement,
    JobMatchScore,
)

from .models import (
    AnalysisRecord,
    CreateJob,
    ImportJob,
    JobFilter,
    JobMatchView,
    JobRecord,
    OpportunityPriorityView,
    PageCursor,
    PagedResult,
    PrioritizeOpportunity,
    RequestContext,
    SyncFromSource,
    SyncFromSourceResult,
    UpdateJob,
    page_result,
)
from .ports import (
    CareerSnapshotProvider,
    Clock,
    IdentifierFactory,
    JobImportProvider,
    JobMatchUnitOfWorkFactory,
    RoleContextProvider,
)
from .job_source_ports import JobSourceConnectorRegistry, JobSourceListing

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class JobMatchPolicy:
    default_page_size: int = 25
    max_page_size: int = 100
    max_saved_jobs: int = 200
    max_requirements: int = 80
    max_sync_listings_per_call: int = 25

    def __post_init__(self) -> None:
        if not 1 <= self.default_page_size <= self.max_page_size <= 200:
            raise ValueError("job match page limits are invalid")
        if self.max_saved_jobs < 1 or not 1 <= self.max_requirements <= 200:
            raise ValueError("job match collection limits are invalid")
        if not 1 <= self.max_sync_listings_per_call <= 100:
            raise ValueError("job match sync limits are invalid")


class JobMatchService:
    """Owner-scoped Phase 5 use cases for jobs, match matrices, and priorities."""

    def __init__(
        self,
        *,
        unit_of_work: JobMatchUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        career_snapshots: CareerSnapshotProvider,
        role_context: RoleContextProvider,
        importer: JobImportProvider,
        job_sources: JobSourceConnectorRegistry | None = None,
        policy: JobMatchPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._career = career_snapshots
        self._roles = role_context
        self._importer = importer
        self._job_sources = job_sources
        self._policy = policy or JobMatchPolicy()

    async def create_job(
        self,
        owner_user_id: UUID,
        command: CreateJob,
        idempotency_key: str,
        context: RequestContext,
    ) -> JobRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "job-create",
            {
                "title": command.title,
                "company": command.company,
                "location": command.location,
                "workModel": command.work_model.value,
                "employmentType": command.employment_type.value,
                "compensation": command.compensation,
                "applicationDeadline": (
                    command.application_deadline.isoformat()
                    if command.application_deadline is not None
                    else None
                ),
                "sourceKind": command.source_kind.value,
                "sourceUrl": command.source_url,
                "sourceTextSha256": _source_sha(command.source_text).hex(),
                "targetRoleId": str(command.target_role_id) if command.target_role_id else None,
            },
        )
        return await self._create_job_record(
            owner_user_id,
            command,
            idempotency_key,
            fingerprint,
            context,
            JobAuditAction.JOB_CREATED,
        )

    async def import_job(
        self,
        owner_user_id: UUID,
        command: ImportJob,
        idempotency_key: str,
        context: RequestContext,
    ) -> JobRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "job-import",
            {
                "url": command.url,
                "targetRoleId": str(command.target_role_id) if command.target_role_id else None,
            },
        )
        async with self._uow() as uow:
            existing = await uow.find_job_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.job.idempotency_fingerprint != fingerprint:
                    raise JobMatchIdempotencyConflict
                return existing
        imported = await self._importer.fetch(command.url)
        create = CreateJob(
            title=imported.title,
            company=imported.company,
            location=imported.location,
            work_model=command_work_model(imported.source_text),
            employment_type=command_employment_type(imported.source_text),
            compensation=None,
            application_deadline=None,
            source_kind=JobSourceKind.URL,
            source_url=imported.final_url,
            source_text=imported.source_text,
            target_role_id=command.target_role_id,
        )
        return await self._create_job_record(
            owner_user_id,
            create,
            idempotency_key,
            fingerprint,
            context,
            JobAuditAction.JOB_IMPORTED,
        )

    async def sync_from_source(
        self,
        owner_user_id: UUID,
        command: SyncFromSource,
        *,
        context: RequestContext,
    ) -> SyncFromSourceResult:
        self._authorize(owner_user_id, context)
        platform = command.platform.strip()
        query = command.query.strip()
        if not platform:
            raise JobMatchValidationError("job source platform is required")
        if self._job_sources is None:
            raise JobMatchValidationError("job source sync is unavailable")
        connector = self._job_sources.resolve(platform)
        source_kind = _source_kind_for_platform(connector.platform)
        listings = await connector.fetch_listings(query)
        limited = listings[: self._policy.max_sync_listings_per_call]
        created: list[JobRecord] = []
        skipped = 0
        now = self._clock.now()
        async with self._uow() as uow:
            for listing in limited:
                _validate_listing(listing)
                existing = await uow.find_job_by_external(
                    owner_user_id,
                    source_kind,
                    listing.external_id,
                )
                if existing is not None:
                    skipped += 1
                    continue
                create = CreateJob(
                    title=listing.title,
                    company=listing.company,
                    location=listing.location,
                    work_model=command_work_model(listing.source_text),
                    employment_type=command_employment_type(listing.source_text),
                    compensation=None,
                    application_deadline=None,
                    source_kind=source_kind,
                    source_url=listing.application_url,
                    external_id=listing.external_id,
                    source_text=listing.source_text,
                    target_role_id=command.target_role_id,
                )
                fingerprint = _fingerprint(
                    "job-sync",
                    {
                        "platform": connector.platform,
                        "externalId": listing.external_id,
                        "targetRoleId": (
                            str(command.target_role_id) if command.target_role_id else None
                        ),
                    },
                )
                idempotency_key = f"sync:{connector.platform}:{listing.external_id}"
                target_role_title = await self._target_role_title(
                    owner_user_id,
                    command.target_role_id,
                )
                extracted = extract_job_content(
                    create.source_text,
                    max_requirements=self._policy.max_requirements,
                )
                job_id = self._ids.new()
                title = _required_title(create.title, extracted.title)
                job = JobPosting(
                    id=job_id,
                    owner_user_id=owner_user_id,
                    title=title,
                    company=create.company or extracted.company,
                    location=create.location or extracted.location,
                    work_model=create.work_model,
                    employment_type=create.employment_type,
                    compensation=create.compensation,
                    application_deadline=create.application_deadline,
                    source_kind=create.source_kind,
                    source_url=create.source_url,
                    external_id=create.external_id,
                    source_text=create.source_text,
                    source_sha256=_source_sha(create.source_text),
                    idempotency_key=idempotency_key,
                    idempotency_fingerprint=fingerprint,
                    target_role_id=create.target_role_id,
                    target_role_title=target_role_title,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                record = JobRecord(
                    job=job,
                    requirements=self._requirements(owner_user_id, job_id, extracted.requirements),
                )
                current = await uow.list_jobs(
                    owner_user_id,
                    JobFilter(),
                    None,
                    self._policy.max_saved_jobs + 1,
                )
                if len(current) + len(created) >= self._policy.max_saved_jobs:
                    raise JobMatchConflict("saved job limit reached")
                await uow.add_job(record)
                created.append(record)
            if created:
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        JobAuditAction.JOBS_SYNCED_FROM_SOURCE,
                        "job_source",
                        created[0].job.id,
                        context,
                        now,
                        job_id=created[0].job.id,
                        reason=(
                            f"platform={connector.platform};"
                            f"created={len(created)};skipped={skipped}"
                        ),
                    )
                )
            await uow.commit()
        return SyncFromSourceResult(created=tuple(created), skipped=skipped)

    async def list_jobs(
        self,
        owner_user_id: UUID,
        filter_by: JobFilter | None = None,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[JobRecord]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            records = await uow.list_jobs(
                owner_user_id, filter_by or JobFilter(), after, page_size + 1
            )
        return page_result(records, cursor=after, limit=page_size)

    async def get_job(self, owner_user_id: UUID, job_id: UUID) -> JobRecord:
        async with self._uow() as uow:
            record = await uow.get_job(owner_user_id, job_id)
        if record is None:
            raise JobMatchNotFound
        return record

    async def update_job(
        self,
        owner_user_id: UUID,
        job_id: UUID,
        expected_version: int,
        command: UpdateJob,
        context: RequestContext,
    ) -> JobRecord:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        target_role_title = await self._target_role_title(owner_user_id, command.target_role_id)
        extracted = extract_job_content(
            command.source_text, max_requirements=self._policy.max_requirements
        )
        title = _required_title(command.title, extracted.title)
        requirements = self._requirements(owner_user_id, job_id, extracted.requirements)
        async with self._uow() as uow:
            record = await uow.get_job(owner_user_id, job_id, for_update=True)
            if record is None:
                raise JobMatchNotFound
            self._version(record.job.version, expected_version)
            record.job.edit(
                title=title,
                company=command.company or extracted.company,
                location=command.location or extracted.location,
                work_model=command.work_model,
                employment_type=command.employment_type,
                compensation=command.compensation,
                application_deadline=command.application_deadline,
                source_text=command.source_text,
                source_sha256=_source_sha(command.source_text),
                target_role_id=command.target_role_id,
                target_role_title=target_role_title,
                now=now,
            )
            updated = JobRecord(job=record.job, requirements=requirements)
            await uow.save_job(updated)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    JobAuditAction.JOB_UPDATED,
                    "job",
                    job_id,
                    context,
                    now,
                    job_id=job_id,
                    target_role_id=command.target_role_id,
                )
            )
            await uow.commit()
            return updated

    async def delete_job(
        self,
        owner_user_id: UUID,
        job_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_job(owner_user_id, job_id, for_update=True)
            if record is None:
                raise JobMatchNotFound
            self._version(record.job.version, expected_version)
            await uow.delete_job(owner_user_id, job_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    JobAuditAction.JOB_DELETED,
                    "job",
                    job_id,
                    context,
                    now,
                    job_id=job_id,
                )
            )
            await uow.commit()

    async def analyze_job(
        self,
        owner_user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
        context: RequestContext,
    ) -> JobMatchView:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        async with self._uow() as uow:
            job_record = await uow.get_job(owner_user_id, job_id)
            if job_record is None:
                raise JobMatchNotFound
            fingerprint = _analysis_fingerprint(job_record.job)
            existing = await uow.find_analysis_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.analysis.idempotency_fingerprint != fingerprint:
                    raise JobMatchIdempotencyConflict
                return self._match_view(job_record, existing)
            snapshot = await self._career.snapshot(owner_user_id)
            score = score_job_match(
                job_record.job,
                tuple(
                    (requirement.id, _extracted_requirement(requirement))
                    for requirement in job_record.requirements
                ),
                snapshot,
            )
            analysis_record = self._analysis_record(
                owner_user_id, job_record.job, idempotency_key, fingerprint, score, now
            )
            await uow.add_analysis(analysis_record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    JobAuditAction.JOB_ANALYZED,
                    "job_match_analysis",
                    analysis_record.analysis.id,
                    context,
                    now,
                    job_id=job_id,
                    analysis_id=analysis_record.analysis.id,
                )
            )
            await uow.commit()
            return self._match_view(job_record, analysis_record)

    async def get_analysis(self, owner_user_id: UUID, analysis_id: UUID) -> JobMatchView:
        async with self._uow() as uow:
            analysis = await uow.get_analysis(owner_user_id, analysis_id)
            if analysis is None:
                raise JobMatchNotFound
            job = await uow.get_job(owner_user_id, analysis.analysis.job_id)
        if job is None:
            raise JobMatchNotFound
        return self._match_view(job, analysis)

    async def get_latest_analysis_for_job(
        self,
        owner_user_id: UUID,
        job_id: UUID,
    ) -> JobMatchView | None:
        """Return the latest owner-scoped analysis through an application boundary."""

        async with self._uow() as uow:
            job = await uow.get_job(owner_user_id, job_id)
            if job is None:
                raise JobMatchNotFound
            analysis = await uow.latest_analysis_for_job(owner_user_id, job_id)
        return self._match_view(job, analysis) if analysis is not None else None

    async def prioritize_opportunity(
        self,
        owner_user_id: UUID,
        job_id: UUID,
        command: PrioritizeOpportunity,
        idempotency_key: str,
        context: RequestContext,
    ) -> OpportunityPriorityView:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        if not 1 <= command.user_interest <= 5 or not 1 <= command.career_direction_fit <= 5:
            raise JobMatchValidationError("priority fit values must be between 1 and 5")
        if not 0 <= command.existing_contacts <= 100:
            raise JobMatchValidationError("existing contacts is out of range")
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job(owner_user_id, job_id)
            if job is None:
                raise JobMatchNotFound
            analysis = (
                await uow.get_analysis(owner_user_id, command.analysis_id)
                if command.analysis_id is not None
                else await uow.latest_analysis_for_job(owner_user_id, job_id)
            )
            if analysis is None or analysis.analysis.job_id != job_id:
                raise JobMatchNotFound
            fingerprint = _priority_fingerprint(job_id, analysis.analysis.id, command)
            existing = await uow.find_priority_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.idempotency_fingerprint != fingerprint:
                    raise JobMatchIdempotencyConflict
                return OpportunityPriorityView(
                    priority=existing, job=job.job, analysis=analysis.analysis
                )
            score = score_opportunity_priority(
                job.job,
                _score_from_analysis(analysis.analysis),
                OpportunityPriorityInput(
                    user_interest=command.user_interest,
                    career_direction_fit=command.career_direction_fit,
                    compensation_fit=command.compensation_fit,
                    location_fit=command.location_fit,
                    work_model_fit=command.work_model_fit,
                    tailoring_effort=command.tailoring_effort,
                    existing_contacts=command.existing_contacts,
                ),
            )
            priority = OpportunityPriorityAnalysis(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                job_id=job_id,
                analysis_id=analysis.analysis.id,
                idempotency_key=idempotency_key,
                idempotency_fingerprint=fingerprint,
                priority_label=score.priority_label,
                priority_score_basis_points=score.priority_score_basis_points,
                input_snapshot=score.input_snapshot,
                reasons_for=score.reasons_for,
                reconsiderations=score.reconsiderations,
                blockers=score.blockers,
                next_action=score.next_action,
                created_at=now,
            )
            await uow.add_priority(priority)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    JobAuditAction.OPPORTUNITY_PRIORITIZED,
                    "opportunity_priority",
                    priority.id,
                    context,
                    now,
                    job_id=job_id,
                    analysis_id=analysis.analysis.id,
                    priority_id=priority.id,
                )
            )
            await uow.commit()
            return OpportunityPriorityView(
                priority=priority, job=job.job, analysis=analysis.analysis
            )

    async def get_priority(self, owner_user_id: UUID, priority_id: UUID) -> OpportunityPriorityView:
        async with self._uow() as uow:
            priority = await uow.get_priority(owner_user_id, priority_id)
            if priority is None:
                raise JobMatchNotFound
            job = await uow.get_job(owner_user_id, priority.job_id)
            analysis = await uow.get_analysis(owner_user_id, priority.analysis_id)
        if job is None or analysis is None:
            raise JobMatchNotFound
        return OpportunityPriorityView(priority=priority, job=job.job, analysis=analysis.analysis)

    async def _create_job_record(
        self,
        owner_user_id: UUID,
        command: CreateJob,
        idempotency_key: str,
        fingerprint: str,
        context: RequestContext,
        action: JobAuditAction,
    ) -> JobRecord:
        now = self._clock.now()
        target_role_title = await self._target_role_title(owner_user_id, command.target_role_id)
        extracted = extract_job_content(
            command.source_text, max_requirements=self._policy.max_requirements
        )
        job_id = self._ids.new()
        title = _required_title(command.title, extracted.title)
        job = JobPosting(
            id=job_id,
            owner_user_id=owner_user_id,
            title=title,
            company=command.company or extracted.company,
            location=command.location or extracted.location,
            work_model=command.work_model,
            employment_type=command.employment_type,
            compensation=command.compensation,
            application_deadline=command.application_deadline,
            source_kind=command.source_kind,
            source_url=command.source_url,
            external_id=command.external_id,
            source_text=command.source_text,
            source_sha256=_source_sha(command.source_text),
            idempotency_key=idempotency_key,
            idempotency_fingerprint=fingerprint,
            target_role_id=command.target_role_id,
            target_role_title=target_role_title,
            version=1,
            created_at=now,
            updated_at=now,
        )
        record = JobRecord(
            job=job,
            requirements=self._requirements(owner_user_id, job_id, extracted.requirements),
        )
        async with self._uow() as uow:
            existing = await uow.find_job_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.job.idempotency_fingerprint != fingerprint:
                    raise JobMatchIdempotencyConflict
                return existing
            current = await uow.list_jobs(
                owner_user_id, JobFilter(), None, self._policy.max_saved_jobs + 1
            )
            if len(current) >= self._policy.max_saved_jobs:
                raise JobMatchConflict("saved job limit reached")
            await uow.add_job(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    action,
                    "job",
                    job.id,
                    context,
                    now,
                    job_id=job.id,
                    target_role_id=command.target_role_id,
                )
            )
            await uow.commit()
            return record

    def _requirements(
        self, owner_user_id: UUID, job_id: UUID, items: tuple[ExtractedRequirement, ...]
    ) -> tuple[JobRequirement, ...]:
        return tuple(
            JobRequirement(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                job_id=job_id,
                requirement_type=item.requirement_type,
                text=item.text,
                normalized_text=item.normalized_text,
                importance=item.importance,
                source_start=item.source_start,
                source_end=item.source_end,
                confidence_basis_points=item.confidence_basis_points,
                sort_order=item.sort_order,
            )
            for item in items
        )

    def _analysis_record(
        self,
        owner_user_id: UUID,
        job: JobPosting,
        idempotency_key: str,
        fingerprint: str,
        score: JobMatchScore,
        created_at: datetime,
    ) -> AnalysisRecord:
        analysis = JobMatchAnalysis(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            job_id=job.id,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=fingerprint,
            engine_version=score.engine_version,
            configuration_version=score.configuration_version,
            feature_schema_version=score.feature_schema_version,
            input_snapshot=score.input_snapshot,
            feature_set_hash=score.feature_set_hash,
            raw_score_basis_points=score.raw_score_basis_points,
            display_score=score.display_score,
            readiness_label=score.readiness_label,
            hard_gap_count=score.hard_gap_count,
            insufficient_reason=score.insufficient_reason,
            summary=score.summary,
            created_at=created_at,
        )
        components = tuple(
            JobMatchComponent(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                analysis_id=analysis.id,
                dimension=item.dimension,
                weight_basis_points=item.weight_basis_points,
                score_basis_points=item.score_basis_points,
                contribution_basis_points=item.contribution_basis_points,
                explanation=item.explanation,
            )
            for item in score.components
        )
        matches: list[RequirementMatch] = []
        links: list[RequirementEvidenceLink] = []
        for item in score.requirement_matches:
            match = RequirementMatch(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                analysis_id=analysis.id,
                requirement_id=item.requirement_id,
                requirement_text=item.requirement_text,
                requirement_type=item.requirement_type,
                importance=item.importance,
                match_state=item.state,
                score_basis_points=item.score_basis_points,
                explanation=item.explanation,
                recommended_action=item.recommended_action,
                hard_gap=item.hard_gap,
            )
            matches.append(match)
            links.extend(
                RequirementEvidenceLink(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    analysis_id=analysis.id,
                    requirement_match_id=match.id,
                    evidence_id=link.evidence_id,
                    evidence_title=link.evidence_title,
                    evidence_strength=link.evidence_strength,
                    relevance_basis_points=link.relevance_basis_points,
                    rationale=link.rationale,
                )
                for link in item.evidence
            )
        return AnalysisRecord(
            analysis=analysis,
            components=components,
            requirement_matches=tuple(matches),
            evidence_links=tuple(links),
        )

    async def _target_role_title(self, owner_user_id: UUID, role_id: UUID | None) -> str | None:
        if role_id is None:
            return None
        return await self._roles.role_title(owner_user_id, role_id)

    def _match_view(self, job: JobRecord, analysis: AnalysisRecord) -> JobMatchView:
        return JobMatchView(
            job=job.job,
            requirements=job.requirements,
            analysis=analysis.analysis,
            components=analysis.components,
            requirement_matches=analysis.requirement_matches,
            evidence_links=analysis.evidence_links,
        )

    def _page_size(self, value: int | None) -> int:
        if value is None:
            return self._policy.default_page_size
        if not 1 <= value <= self._policy.max_page_size:
            raise JobMatchValidationError("page limit is out of range")
        return value

    def _authorize(self, owner_user_id: UUID, context: RequestContext) -> None:
        if owner_user_id != context.actor_user_id:
            raise JobMatchNotFound

    @staticmethod
    def _idempotency(value: str) -> None:
        if _IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise JobMatchValidationError("idempotency key is invalid")

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if not 1 <= expected <= 2_147_483_647:
            raise JobMatchValidationError("expected version must be a positive int32")
        if actual != expected:
            raise JobMatchVersionConflict

    def _audit(
        self,
        owner_user_id: UUID,
        action: JobAuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        created_at: datetime,
        **details: UUID | None,
    ) -> JobMatchAuditEvent:
        return JobMatchAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            actor_user_id=context.actor_user_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            details=tuple((key, str(value)) for key, value in details.items() if value is not None),
            created_at=created_at,
        )


def command_work_model(source_text: str) -> WorkModel:
    normalized = source_text.casefold()
    if "remote" in normalized:
        return WorkModel.REMOTE
    if "hybrid" in normalized:
        return WorkModel.HYBRID
    if "onsite" in normalized or "on-site" in normalized:
        return WorkModel.ONSITE
    return WorkModel.UNKNOWN


def command_employment_type(source_text: str) -> EmploymentType:
    normalized = source_text.casefold()
    if "part-time" in normalized or "part time" in normalized:
        return EmploymentType.PART_TIME
    if "contract" in normalized:
        return EmploymentType.CONTRACT
    if "intern" in normalized:
        return EmploymentType.INTERNSHIP
    if "temporary" in normalized:
        return EmploymentType.TEMPORARY
    if "full-time" in normalized or "full time" in normalized:
        return EmploymentType.FULL_TIME
    return EmploymentType.UNKNOWN


def _required_title(explicit: str | None, extracted: str | None) -> str:
    title = explicit or extracted
    if title is None or not title.strip():
        raise JobMatchValidationError("job title is required")
    return title


def _extracted_requirement(requirement: JobRequirement) -> ExtractedRequirement:
    return ExtractedRequirement(
        requirement_type=requirement.requirement_type,
        text=requirement.text,
        normalized_text=requirement.normalized_text,
        importance=requirement.importance,
        source_start=requirement.source_start,
        source_end=requirement.source_end,
        confidence_basis_points=requirement.confidence_basis_points,
        sort_order=requirement.sort_order,
    )


def _score_from_analysis(analysis: JobMatchAnalysis) -> JobMatchScore:
    return JobMatchScore(
        engine_version=analysis.engine_version,
        configuration_version=analysis.configuration_version,
        feature_schema_version=analysis.feature_schema_version,
        feature_set_hash=analysis.feature_set_hash,
        input_snapshot=analysis.input_snapshot,
        raw_score_basis_points=analysis.raw_score_basis_points,
        display_score=analysis.display_score,
        readiness_label=analysis.readiness_label,
        hard_gap_count=analysis.hard_gap_count,
        insufficient_reason=analysis.insufficient_reason,
        summary=analysis.summary,
        components=(),
        requirement_matches=(),
    )


def _analysis_fingerprint(job: JobPosting) -> str:
    return _fingerprint(
        "job-analysis",
        {
            "jobId": str(job.id),
            "jobVersion": job.version,
            "sourceSha256": job.source_sha256.hex(),
        },
    )


def _priority_fingerprint(job_id: UUID, analysis_id: UUID, command: PrioritizeOpportunity) -> str:
    return _fingerprint(
        "opportunity-priority",
        {
            "jobId": str(job_id),
            "analysisId": str(analysis_id),
            "userInterest": command.user_interest,
            "careerDirectionFit": command.career_direction_fit,
            "compensationFit": command.compensation_fit.value,
            "locationFit": command.location_fit.value,
            "workModelFit": command.work_model_fit.value,
            "tailoringEffort": command.tailoring_effort.value,
            "existingContacts": command.existing_contacts,
        },
    )


def _source_sha(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def _fingerprint(kind: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(
        {"kind": kind, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _source_kind_for_platform(platform: str) -> JobSourceKind:
    mapping = {
        "greenhouse": JobSourceKind.GREENHOUSE,
        "fake": JobSourceKind.FAKE,
    }
    kind = mapping.get(platform.strip().casefold())
    if kind is None:
        raise JobMatchValidationError("job source platform is not supported")
    return kind


def _validate_listing(listing: JobSourceListing) -> None:
    if not listing.external_id.strip():
        raise JobMatchValidationError("listing external id is invalid")
    if not listing.title.strip():
        raise JobMatchValidationError("listing title is invalid")
    if len(listing.source_text.strip()) < 20:
        raise JobMatchValidationError("listing source text is invalid")
    if listing.application_url is not None and not listing.application_url.startswith(
        ("https://", "http://")
    ):
        raise JobMatchValidationError("listing application URL is invalid")
