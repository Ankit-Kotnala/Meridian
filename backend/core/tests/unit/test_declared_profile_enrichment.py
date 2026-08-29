"""Phase 11 declared-link enrichment tests."""

import json
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from career_record_memory import FakeResumeSourceQuery, FixedClock, MemoryCareerRecord, UuidFactory

from rezumi.modules.career_record.application import (
    CareerRecordService,
    CreatePersonalFact,
    EvidenceFilter,
    RequestContext,
)
from rezumi.modules.career_record.application.declared_profile_enrichment import (
    DeclaredProfileEnrichmentService,
)
from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileUnsupported,
)
from rezumi.modules.career_record.domain import PersonalFactKind
from rezumi.modules.career_record.infrastructure.declared_profile.credly_connector import (
    CredlyDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.fake_connector import (
    FakeDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.portfolio_connector import (
    PortfolioDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.registry import (
    DeclaredProfileConnectorRegistry,
)
from rezumi.modules.career_record.infrastructure.declared_profile.safe_http import SafeHttpPage

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _context(owner) -> RequestContext:
    return RequestContext(owner, "request-enrich", "trace-enrich")


def _service(memory: MemoryCareerRecord) -> CareerRecordService:
    return CareerRecordService(
        unit_of_work=memory,
        clock=FixedClock(NOW),
        identifiers=UuidFactory(),
        resume_sources=FakeResumeSourceQuery(),
    )


@pytest.mark.asyncio
async def test_enrich_declared_link_creates_achievements_and_evidence() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    career = _service(memory)
    await career.get_or_create_profile(owner, _context(owner))
    fact = await career.create_personal_fact(
        owner,
        CreatePersonalFact(
            kind=PersonalFactKind.LINK,
            value="https://example.test/profile/alex",
            label="Portfolio",
        ),
        _context(owner),
    )
    enrichment = DeclaredProfileEnrichmentService(
        career_record=career,
        connectors=DeclaredProfileConnectorRegistry((FakeDeclaredProfileConnector(),)),
    )

    result = await enrichment.enrich_personal_fact(owner, fact.id, _context(owner))

    assert result.platform == "fake"
    assert result.achievements_created == 2
    assert result.evidence_created == 2
    achievements = await career.list_achievements(owner, limit=10)
    assert len(achievements.items) == 2
    evidence = await career.list_evidence(owner, filter_by=EvidenceFilter(), limit=10)
    assert len(evidence.items) == 2


@pytest.mark.asyncio
async def test_linkedin_declared_link_is_rejected_with_clear_message() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    career = _service(memory)
    await career.get_or_create_profile(owner, _context(owner))
    fact = await career.create_personal_fact(
        owner,
        CreatePersonalFact(
            kind=PersonalFactKind.LINK,
            value="https://linkedin.com/in/alex-example",
        ),
        _context(owner),
    )
    enrichment = DeclaredProfileEnrichmentService(
        career_record=career,
        connectors=DeclaredProfileConnectorRegistry((FakeDeclaredProfileConnector(),)),
    )

    with pytest.raises(DeclaredProfileUnsupported, match="LinkedIn"):
        await enrichment.enrich_personal_fact(owner, fact.id, _context(owner))


class _StubFetcher:
    async def fetch(self, url: str) -> SafeHttpPage:
        _ = url
        return SafeHttpPage(
            final_url="https://portfolio.example/projects",
            title="Alex Portfolio",
            text=(
                "Built API gateway — reduced latency 40%\n"
                "Led migration to Kubernetes — zero downtime cutover\n"
                "Copyright 2026"
            ),
        )


@pytest.mark.asyncio
async def test_portfolio_connector_extracts_heading_achievements() -> None:
    connector = PortfolioDeclaredProfileConnector(fetcher=_StubFetcher())
    assert connector.supports("https://portfolio.example/projects")
    assert not connector.supports("https://github.com/alex")

    result = await connector.fetch("https://portfolio.example/projects")

    assert result.platform == "portfolio"
    assert len(result.achievements) == 2
    assert result.achievements[0].title == "Built API gateway"
    assert "latency" in result.achievements[0].excerpt


class _FakeCredlyResponse:
    def __init__(self, payload: dict) -> None:
        self._buffer = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, _size: int) -> bytes:
        return self._buffer.read()

    def __enter__(self) -> "_FakeCredlyResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def test_credly_connector_supports_user_badge_urls() -> None:
    connector = CredlyDeclaredProfileConnector()
    assert connector.supports("https://credly.com/users/alex-example")
    assert not connector.supports("https://credly.com/organizations/acme")
    assert not connector.supports("https://github.com/alex")


@pytest.mark.asyncio
async def test_credly_connector_extracts_badges_from_public_feed() -> None:
    connector = CredlyDeclaredProfileConnector()
    payload = {
        "data": [
            {
                "badge_template": {
                    "name": "Certified Kubernetes Administrator",
                    "issuer": {"entities": [{"entity": {"name": "The Linux Foundation"}}]},
                },
                "issued_at": "2026-01-15",
                "public_url": "https://credly.com/badges/abc123",
            }
        ]
    }

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.credly_connector.urlopen",
        return_value=_FakeCredlyResponse(payload),
    ):
        result = await connector.fetch("https://credly.com/users/alex-example")

    assert result.platform == "credly"
    assert len(result.achievements) == 1
    assert result.achievements[0].title == "Certified Kubernetes Administrator"
    assert "Linux Foundation" in result.achievements[0].statement

