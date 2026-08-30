"""Materialize declared-link fetches into achievement drafts and evidence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileFetchFailed,
    normalize_declared_profile_url,
)
from rezumi.modules.career_record.application.models import (
    CreateAchievement,
    CreateEvidence,
    RequestContext,
)
from rezumi.modules.career_record.application.service import CareerRecordService
from rezumi.modules.career_record.domain import (
    EvidenceInputKind,
    EvidenceType,
    PersonalFactKind,
)
from rezumi.modules.career_record.domain.errors import CareerRecordNotFound
from rezumi.modules.career_record.infrastructure.declared_profile.registry import (
    DeclaredProfileConnectorRegistry,
)

_DEDUPE_PAGE_SIZE = 100
_MAX_DEDUPE_PAGES = 20


@dataclass(frozen=True, slots=True)
class DeclaredProfileEnrichmentResult:
    platform: str
    profile_url: str
    achievements_created: int
    evidence_created: int
    skipped_duplicates: int


class DeclaredProfileEnrichmentService:
    def __init__(
        self,
        *,
        career_record: CareerRecordService,
        connectors: DeclaredProfileConnectorRegistry,
    ) -> None:
        self._career_record = career_record
        self._connectors = connectors

    async def _existing_titles(self, owner_user_id: UUID) -> set[str]:
        """Every achievement title already on record, not just the first page.

        The duplicate check has to see the whole record: reading one page meant
        a re-run imported the same profile again for anyone holding more
        achievements than a page, quietly doubling their evidence.
        """

        titles: set[str] = set()
        cursor: str | None = None
        for _ in range(_MAX_DEDUPE_PAGES):
            page = await self._career_record.list_achievements(
                owner_user_id, cursor=cursor, limit=_DEDUPE_PAGE_SIZE
            )
            titles.update(item.title.strip().casefold() for item in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        return titles

    async def enrich_personal_fact(
        self,
        owner_user_id: UUID,
        fact_id: UUID,
        context: RequestContext,
    ) -> DeclaredProfileEnrichmentResult:
        fact = await self._career_record.get_personal_fact(owner_user_id, fact_id)
        if fact.kind is not PersonalFactKind.LINK:
            raise CareerRecordNotFound
        profile_url = normalize_declared_profile_url(fact.value)
        connector = self._connectors.resolve(profile_url)
        try:
            fetched = await connector.fetch(profile_url)
        except DeclaredProfileFetchFailed:
            raise

        existing_titles = await self._existing_titles(owner_user_id)

        achievements_created = 0
        evidence_created = 0
        skipped = 0

        for candidate in fetched.achievements:
            key = candidate.title.strip().casefold()
            if key in existing_titles:
                skipped += 1
                continue
            await self._career_record.create_achievement(
                owner_user_id,
                CreateAchievement(
                    title=candidate.title,
                    delivered=candidate.statement,
                ),
                context,
            )
            existing_titles.add(key)
            achievements_created += 1

            await self._career_record.create_evidence(
                owner_user_id,
                CreateEvidence(
                    evidence_type=EvidenceType.PORTFOLIO,
                    title=candidate.title,
                    statement=candidate.statement,
                    context=f"Imported from {fetched.platform} profile",
                    input_kind=EvidenceInputKind.MANUAL,
                    external_url_source=candidate.source_url,
                ),
                context,
            )
            evidence_created += 1

        return DeclaredProfileEnrichmentResult(
            platform=fetched.platform,
            profile_url=fetched.profile_url,
            achievements_created=achievements_created,
            evidence_created=evidence_created,
            skipped_duplicates=skipped,
        )
