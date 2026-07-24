"""Application-boundary source providers for Phase 7 resume creation."""

from __future__ import annotations

from uuid import UUID

from careeros.modules.career_record.application import CareerRecordService
from careeros.modules.change_studio.application import ChangeStudioService
from careeros.modules.resume_builder.application import (
    ResumeSourceBullet,
    ResumeSourceSnapshot,
)
from careeros.modules.resume_builder.application.ports import ResumeSourceProvider
from careeros.modules.resume_builder.domain import ResumeBuilderValidationError


class CareerRecordResumeSourceProvider(ResumeSourceProvider):
    """Build a grounded resume source snapshot from existing application services."""

    def __init__(
        self,
        career_record: CareerRecordService,
        *,
        change_studio: ChangeStudioService | None = None,
    ) -> None:
        self._career_record = career_record
        self._change_studio = change_studio

    async def snapshot(
        self,
        owner_user_id: UUID,
        *,
        change_set_id: UUID | None = None,
        change_set_version_id: UUID | None = None,
    ) -> ResumeSourceSnapshot:
        try:
            profile = await self._career_record.get_profile(owner_user_id)
            readiness = await self._career_record.readiness_snapshot(owner_user_id)
        except Exception as exc:
            raise ResumeBuilderValidationError(
                "career record must exist before building a resume"
            ) from exc

        evidence_ids = tuple(item.id for item in readiness.evidence)
        bullets: list[ResumeSourceBullet] = [
            ResumeSourceBullet(
                text=item.statement,
                evidence_ids=(item.id,),
                source="career_record",
            )
            for item in readiness.evidence
        ]
        for skill in readiness.skills:
            linked = tuple(
                evidence.id for evidence in readiness.evidence if skill.id in evidence.skill_ids
            )
            if linked:
                bullets.append(
                    ResumeSourceBullet(
                        text=skill.name,
                        evidence_ids=linked[:3],
                        source="career_record",
                    )
                )

        if change_set_id is not None:
            bullets.extend(
                await self._change_studio_bullets(
                    owner_user_id,
                    change_set_id,
                    change_set_version_id,
                    fallback_evidence_ids=evidence_ids,
                )
            )

        return ResumeSourceSnapshot(
            headline=profile.profile.professional_headline,
            summary=profile.profile.summary,
            skills=tuple(
                skill.name
                for skill in readiness.skills
                if any(skill.id in evidence.skill_ids for evidence in readiness.evidence)
            ),
            bullets=tuple(dict.fromkeys(bullets)),
            source_evidence_ids=evidence_ids,
        )

    async def _change_studio_bullets(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        change_set_version_id: UUID | None,
        *,
        fallback_evidence_ids: tuple[UUID, ...],
    ) -> tuple[ResumeSourceBullet, ...]:
        if self._change_studio is None:
            raise ResumeBuilderValidationError("change studio source is unavailable")
        try:
            record = await self._change_studio.get_change_set(owner_user_id, change_set_id)
        except Exception as exc:
            raise ResumeBuilderValidationError("change studio source is unavailable") from exc
        version = None
        for candidate in record.versions:
            if candidate.id == change_set_version_id or (
                change_set_version_id is None
                and candidate.id == record.change_set.current_version_id
            ):
                version = candidate
                break
        if version is None:
            raise ResumeBuilderValidationError("change studio version is unavailable")
        claim_evidence = tuple(dict.fromkeys(claim.evidence_id for claim in record.claims))
        evidence_ids = claim_evidence or fallback_evidence_ids
        if not evidence_ids:
            return ()
        return tuple(
            ResumeSourceBullet(
                text=line.strip("- ").strip(),
                evidence_ids=evidence_ids[:3],
                source="change_studio",
            )
            for line in version.content.splitlines()
            if line.strip("- ").strip()
        )
