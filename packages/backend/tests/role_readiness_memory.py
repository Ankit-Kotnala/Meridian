"""Deterministic in-memory Role Readiness ports for focused service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import TracebackType
from uuid import UUID, uuid4

from careeros.modules.role_readiness.application.models import (
    AnalysisRecord,
    PageCursor,
    RoleFilter,
    RoleReadinessAnalyticsPoint,
    RoleReadinessAnalyticsSourceState,
)
from careeros.modules.role_readiness.domain import (
    CompetencyDimension,
    CompetencyImportance,
    RoleCompetency,
    RoleDefinition,
    RoleReadinessAuditEvent,
    RoleSeniority,
    RoleTaxonomyVersion,
    SavedRole,
)
from careeros.modules.role_readiness.domain.scoring import (
    CareerReadinessSnapshot,
    SnapshotEvidence,
    SnapshotSkill,
)

NOW = datetime(2026, 7, 19, 12, tzinfo=UTC)
TAXONOMY_ID = UUID("00000000-0000-4000-8000-000000000401")
PRODUCT_ROLE_ID = UUID("00000000-0000-4000-8000-000000000411")
ENGINEER_ROLE_ID = UUID("00000000-0000-4000-8000-000000000412")


class FixedClock:
    def __init__(self, value: datetime | None = None) -> None:
        self.value = value or NOW

    def now(self) -> datetime:
        return self.value


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()


class StaticSnapshotProvider:
    def __init__(self, snapshot: CareerReadinessSnapshot) -> None:
        self.snapshot_value = snapshot
        self.requests: list[UUID] = []

    async def snapshot(self, owner_user_id: UUID) -> CareerReadinessSnapshot:
        self.requests.append(owner_user_id)
        return self.snapshot_value


def sample_readiness_snapshot() -> CareerReadinessSnapshot:
    skill_id = UUID("00000000-0000-4000-8000-000000000701")
    return CareerReadinessSnapshot(
        skills=(SnapshotSkill(skill_id, "User research", "Product", "advanced"),),
        entities=(),
        evidence=(
            SnapshotEvidence(
                id=UUID("00000000-0000-4000-8000-000000000801"),
                title="Confirmed customer discovery",
                statement="Confirmed evidence about user research with customers.",
                context="The owner confirmed the evidence in the evidence vault.",
                strength="confirmed",
                skill_ids=(skill_id,),
                entity_ids=(),
                has_numeric_claim=False,
            ),
        ),
    )


class MemoryRoleReadiness:
    def __init__(self) -> None:
        self.taxonomies: dict[UUID, RoleTaxonomyVersion] = {}
        self.roles: dict[UUID, RoleDefinition] = {}
        self.competencies: dict[UUID, list[RoleCompetency]] = {}
        self.saved_roles: dict[UUID, SavedRole] = {}
        self.analyses: dict[UUID, AnalysisRecord] = {}
        self.audits: list[RoleReadinessAuditEvent] = []
        self.seed()

    def seed(self) -> None:
        taxonomy = RoleTaxonomyVersion(
            id=TAXONOMY_ID,
            version="careeros-seed-roles/2026-07-19",
            source_name="CareerOS authored seed taxonomy",
            source_license="CareerOS internal product taxonomy",
            description="Test taxonomy.",
            active=True,
            published_at=NOW,
            created_at=NOW,
        )
        self.taxonomies[taxonomy.id] = taxonomy
        self.roles[PRODUCT_ROLE_ID] = _role(PRODUCT_ROLE_ID, "product-manager", "Product Manager")
        self.roles[ENGINEER_ROLE_ID] = _role(
            ENGINEER_ROLE_ID, "software-engineer", "Software Engineer"
        )
        self.competencies[PRODUCT_ROLE_ID] = [
            _competency(
                PRODUCT_ROLE_ID,
                1,
                CompetencyDimension.CORE_COMPETENCY,
                "Customer discovery",
                CompetencyImportance.REQUIRED,
                ("user research", "customer discovery"),
                ("research", "customer"),
            ),
            _competency(
                PRODUCT_ROLE_ID,
                2,
                CompetencyDimension.BUSINESS_IMPACT,
                "Measured product outcome",
                CompetencyImportance.REQUIRED,
                ("product metrics", "business impact"),
                ("adoption", "conversion", "reduced"),
            ),
        ]
        self.competencies[ENGINEER_ROLE_ID] = [
            _competency(
                ENGINEER_ROLE_ID,
                3,
                CompetencyDimension.CORE_COMPETENCY,
                "Production programming",
                CompetencyImportance.REQUIRED,
                ("python", "typescript"),
                ("built", "implemented"),
            )
        ]

    def __call__(self) -> MemoryRoleReadiness:
        return self

    async def __aenter__(self) -> MemoryRoleReadiness:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def get_taxonomy_version(self, taxonomy_id: UUID) -> RoleTaxonomyVersion | None:
        return self.taxonomies.get(taxonomy_id)

    async def get_active_taxonomy(self) -> RoleTaxonomyVersion | None:
        return next((item for item in self.taxonomies.values() if item.active), None)

    async def get_role(self, role_id: UUID) -> RoleDefinition | None:
        return self.roles.get(role_id)

    async def list_roles(
        self, filter_by: RoleFilter, after: PageCursor | None, limit: int
    ) -> list[RoleDefinition]:
        values = sorted(self.roles.values(), key=lambda item: (item.title, str(item.id)))
        if filter_by.query is not None:
            query = filter_by.query.casefold()
            values = [
                role
                for role in values
                if query
                in " ".join((role.title, role.industry, role.domain, role.description)).casefold()
            ]
        if filter_by.seniority is not None:
            values = [role for role in values if role.seniority is filter_by.seniority]
        offset = after.offset if after is not None else 0
        return values[offset : offset + limit]

    async def list_role_competencies(self, role_id: UUID) -> list[RoleCompetency]:
        return list(self.competencies.get(role_id, ()))

    async def get_saved_role(
        self, owner_user_id: UUID, saved_role_id: UUID, *, for_update: bool = False
    ) -> SavedRole | None:
        del for_update
        saved = self.saved_roles.get(saved_role_id)
        return saved if saved is not None and saved.owner_user_id == owner_user_id else None

    async def get_saved_role_by_role(
        self, owner_user_id: UUID, role_id: UUID, *, for_update: bool = False
    ) -> SavedRole | None:
        del for_update
        return next(
            (
                saved
                for saved in self.saved_roles.values()
                if saved.owner_user_id == owner_user_id and saved.role_id == role_id
            ),
            None,
        )

    async def list_saved_roles(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[SavedRole]:
        values = sorted(
            [item for item in self.saved_roles.values() if item.owner_user_id == owner_user_id],
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return values[offset : offset + limit]

    async def add_saved_role(self, saved_role: SavedRole) -> None:
        self.saved_roles[saved_role.id] = saved_role

    async def save_saved_role(self, saved_role: SavedRole) -> None:
        self.saved_roles[saved_role.id] = saved_role

    async def delete_saved_role(self, owner_user_id: UUID, saved_role_id: UUID) -> None:
        saved = await self.get_saved_role(owner_user_id, saved_role_id)
        if saved is not None:
            del self.saved_roles[saved.id]

    async def add_analysis(self, record: AnalysisRecord) -> None:
        self.analyses[record.analysis.id] = record

    async def get_analysis(self, owner_user_id: UUID, analysis_id: UUID) -> AnalysisRecord | None:
        record = self.analyses.get(analysis_id)
        return (
            record
            if record is not None and record.analysis.owner_user_id == owner_user_id
            else None
        )

    async def list_analyses(
        self, owner_user_id: UUID, role_id: UUID | None, after: PageCursor | None, limit: int
    ) -> list[AnalysisRecord]:
        values = [
            record
            for record in self.analyses.values()
            if record.analysis.owner_user_id == owner_user_id
            and (role_id is None or record.analysis.role_id == role_id)
        ]
        values.sort(key=lambda item: (item.analysis.created_at, item.analysis.id), reverse=True)
        offset = after.offset if after is not None else 0
        return values[offset : offset + limit]

    async def find_analysis_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AnalysisRecord | None:
        return next(
            (
                record
                for record in self.analyses.values()
                if record.analysis.owner_user_id == owner_user_id
                and record.analysis.idempotency_key == idempotency_key
            ),
            None,
        )

    async def list_analytics_history(
        self,
        owner_user_id: UUID,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> list[RoleReadinessAnalyticsPoint]:
        return [
            RoleReadinessAnalyticsPoint(
                analysis_id=record.analysis.id,
                role_label=self.roles[record.analysis.role_id].title,
                raw_score_basis_points=record.analysis.raw_score_basis_points,
                label=record.analysis.readiness_label.value,
                engine_version=record.analysis.engine_version,
                created_at=record.analysis.created_at,
            )
            for record in sorted(
                self.analyses.values(),
                key=lambda value: (value.analysis.created_at, str(value.analysis.id)),
            )
            if record.analysis.owner_user_id == owner_user_id
            and window_start <= record.analysis.created_at.date() <= window_end
        ][:limit]

    async def get_analytics_source_state(
        self,
        owner_user_id: UUID,
    ) -> RoleReadinessAnalyticsSourceState:
        records = [
            record
            for record in self.analyses.values()
            if record.analysis.owner_user_id == owner_user_id
        ]
        roles = [self.roles[record.analysis.role_id] for record in records]
        return RoleReadinessAnalyticsSourceState(
            record_count=len(records),
            role_version_sum=sum(role.version for role in roles),
            max_analysis_created_at=max(
                (record.analysis.created_at for record in records),
                default=None,
            ),
            max_role_updated_at=max(
                (role.updated_at for role in roles),
                default=None,
            ),
        )

    async def add_audit(self, event: RoleReadinessAuditEvent) -> None:
        self.audits.append(event)

    async def commit(self) -> None:
        return None


def _role(role_id: UUID, slug: str, title: str) -> RoleDefinition:
    return RoleDefinition(
        id=role_id,
        taxonomy_version_id=TAXONOMY_ID,
        slug=slug,
        title=title,
        seniority=RoleSeniority.SENIOR if "product" in slug else RoleSeniority.MID,
        industry="Technology",
        domain="Product" if "product" in slug else "Engineering",
        location_scope="global",
        company_type="software",
        description=f"{title} seed role.",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _competency(
    role_id: UUID,
    suffix: int,
    dimension: CompetencyDimension,
    label: str,
    importance: CompetencyImportance,
    skill_keywords: tuple[str, ...],
    evidence_keywords: tuple[str, ...],
) -> RoleCompetency:
    return RoleCompetency(
        id=UUID(f"00000000-0000-4000-8000-0000000005{suffix:02d}"),
        role_id=role_id,
        dimension=dimension,
        label=label,
        description=f"{label} evidence.",
        importance=importance,
        skill_keywords=skill_keywords,
        evidence_keywords=evidence_keywords,
        transferable_keywords=("planning",),
        adjacent_keywords=("coordination",),
        sort_order=suffix,
    )
