"""Cross-domain declared-link coverage: finance, research, design, management."""

from __future__ import annotations

import gzip
import json
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileUnsupported,
)
from rezumi.modules.career_record.infrastructure.declared_profile.openalex_connector import (
    OpenAlexDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.platform_policy import (
    API_PLATFORM_DOMAINS,
    BLOCKED_PLATFORMS,
)
from rezumi.modules.career_record.infrastructure.declared_profile.registry import (
    default_declared_profile_registry,
)
from rezumi.modules.career_record.infrastructure.declared_profile.stackexchange_connector import (
    StackExchangeDeclaredProfileConnector,
)
from rezumi.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    SectionKind,
    SemanticFieldType,
    SourceSpan,
)
from rezumi.modules.resume_health.infrastructure.semantic_parser import (
    LocalResumeParserProvider,
)


class _FakeJsonResponse:
    def __init__(self, payload: object, *, gzipped: bool = False) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self._buffer = BytesIO(gzip.compress(raw) if gzipped else raw)

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self) -> _FakeJsonResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class _SequencedResponses:
    """Return a different payload per call, in order."""

    def __init__(self, *payloads: object) -> None:
        self._payloads = list(payloads)

    def __call__(self, *_: object, **__: object) -> _FakeJsonResponse:
        return _FakeJsonResponse(self._payloads.pop(0))


# --- Resume-side extraction across domains ---------------------------------


async def _contact_links(text: str) -> list[str]:
    resume = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.CONTACT,
                title="Contact",
                confidence_basis_points=9_000,
                blocks=(
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.PARAGRAPH,
                        text=text,
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 0, len(text)),),
                    ),
                ),
            ),
        ),
        warnings=(),
    )
    semantics = await LocalResumeParserProvider().parse(
        uuid4(), resume, sha256(b"fictional").hexdigest()
    )
    return [
        field.value
        for entity in semantics.entities
        for field in entity.fields
        if field.field_type is SemanticFieldType.URL
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("domain", "link"),
    [
        ("finance", "quant.stackexchange.com/users/848/bob"),
        ("finance", "papers.ssrn.com/sol3/papers.cfm?abstract_id=123456"),
        ("finance", "brokercheck.finra.org/individual/summary/1234567"),
        ("research", "orcid.org/0000-0003-1613-5981"),
        ("research", "pubmed.ncbi.nlm.nih.gov/31452104"),
        ("research", "arxiv.org/a/rivera_a_1"),
        ("management", "speakerdeck.com/alexrivera"),
        ("management", "alexrivera.substack.com/p/operating-cadence"),
        ("design", "behance.net/alexrivera"),
        ("design", "dribbble.com/alexrivera"),
        ("medicine", "doximity.com/pub/alex-rivera-md"),
        ("law", "law.stackexchange.com/users/1/alex"),
        ("credentials", "credly.com/users/alex-rivera"),
        ("credentials", "credential.net/1a2b3c4d"),
        ("ai", "huggingface.co/alex-rivera"),
        ("platform", "hub.docker.com/u/alex-rivera"),
        ("personal-site", "alexrivera.notion.site/portfolio"),
    ],
)
async def test_links_from_every_domain_are_extracted(domain: str, link: str) -> None:
    """A link Rezumi cannot auto-read must still be captured from the resume."""

    _ = domain
    assert await _contact_links(f"Alex Rivera | alex@example.test | {link}") == [link]


# --- Stack Exchange network -------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://stackoverflow.com/users/22656/jon-skeet",
        "https://quant.stackexchange.com/users/848/bob-jansen",
        "https://law.stackexchange.com/users/1/alex",
        "https://academia.stackexchange.com/users/1/alex",
        "https://stats.stackexchange.com/users/1/alex",
        "https://workplace.stackexchange.com/users/1/alex",
        "https://mathoverflow.net/users/1/alex",
        "https://serverfault.com/users/1/alex",
        "https://pt.stackoverflow.com/users/1/alex",
    ],
)
def test_stack_exchange_covers_the_whole_network(url: str) -> None:
    assert StackExchangeDeclaredProfileConnector().supports(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://meta.stackexchange.com/users/1/alex",
        "https://meta.stackoverflow.com/users/1/alex",
        "https://stackoverflow.com/questions/1",
        "https://quant.stackexchange.com/questions/1",
    ],
)
def test_stack_exchange_rejects_meta_sites_and_non_profile_paths(url: str) -> None:
    assert not StackExchangeDeclaredProfileConnector().supports(url)


@pytest.mark.asyncio
async def test_stack_exchange_names_the_site_it_read() -> None:
    connector = StackExchangeDeclaredProfileConnector()
    payload = {
        "items": [
            {
                "display_name": "Bob Jansen",
                "reputation": 8764,
                "badge_counts": {"gold": 8, "silver": 41, "bronze": 61},
                "link": "https://quant.stackexchange.com/users/848/bob-jansen",
            }
        ]
    }

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile."
        "stackexchange_connector.urlopen",
        return_value=_FakeJsonResponse(payload),
    ):
        result = await connector.fetch("https://quant.stackexchange.com/users/848/bob-jansen")

    assert result.platform == "stackexchange"
    assert result.achievements[0].title == "Bob Jansen on quant.stackexchange.com"
    assert "8764 reputation on quant.stackexchange.com" in result.achievements[0].statement
    assert "Powered by Stack Exchange" in result.achievements[0].statement


# --- OpenAlex ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "supported"),
    [
        ("https://orcid.org/0000-0003-1613-5981", True),
        ("https://orcid.org/0000-0002-1825-097X", True),
        ("https://openalex.org/A5048491430", True),
        ("https://openalex.org/authors/A5048491430", True),
        ("https://orcid.org/not-an-orcid", False),
        ("https://openalex.org/W123", False),
    ],
)
def test_openalex_supports_research_identifiers(url: str, supported: bool) -> None:
    assert OpenAlexDeclaredProfileConnector().supports(url) is supported


@pytest.mark.asyncio
async def test_openalex_reports_output_and_top_cited_works() -> None:
    author = {
        "id": "https://openalex.org/A5048491430",
        "display_name": "Heather Piwowar",
        "works_count": 99,
        "cited_by_count": 5656,
        "summary_stats": {"h_index": 24},
        "last_known_institutions": [{"display_name": "OpenAlex"}],
    }
    works = {
        "results": [
            {
                "title": "The state of OA",
                "publication_year": 2018,
                "cited_by_count": 1250,
                "doi": "https://doi.org/10.7717/peerj.4375",
                "primary_location": {"source": {"display_name": "PeerJ"}},
            }
        ]
    }

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.openalex_connector.urlopen",
        side_effect=_SequencedResponses(author, works),
    ):
        result = await OpenAlexDeclaredProfileConnector().fetch(
            "https://orcid.org/0000-0003-1613-5981"
        )

    assert result.platform == "openalex"
    summary = result.achievements[0]
    assert summary.title == "Heather Piwowar on OpenAlex"
    assert "99 indexed works, 5656 citations, h-index 24." in summary.statement
    assert "Last known affiliation: OpenAlex." in summary.statement
    assert "Source: OpenAlex (CC0)." in summary.statement
    work = result.achievements[1]
    assert work.title == "The state of OA"
    assert "Published in PeerJ, 2018." in work.statement
    assert "1250 citations." in work.statement
    assert work.source_url == "https://doi.org/10.7717/peerj.4375"


# --- Cross-domain routing policy -------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.glassdoor.com/profile/alex", "Glassdoor"),
        ("https://wellfound.com/u/alex", "Wellfound"),
        ("https://www.researchgate.net/profile/Alex", "ResearchGate"),
        ("https://scholar.google.com/citations?user=abc", "Google Scholar"),
        ("https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1", "SSRN"),
        ("https://brokercheck.finra.org/individual/summary/1", "FINRA BrokerCheck"),
        ("https://adviserinfo.sec.gov/individual/summary/1", "SEC IAPD"),
        ("https://www.doximity.com/pub/alex-rivera-md", "Doximity"),
        ("https://www.avvo.com/attorneys/alex", "legal directory"),
        ("https://www.coursera.org/account/accomplishments/verify/ABC", "Coursera"),
        ("https://www.figma.com/@alex", "Figma"),
        ("https://www.upwork.com/freelancers/alex", "Upwork"),
        ("https://www.youtube.com/@alex", "YouTube"),
    ],
)
def test_cross_domain_platforms_refuse_with_a_reason_not_scraped_junk(
    url: str, expected: str
) -> None:
    registry = default_declared_profile_registry()
    with pytest.raises(DeclaredProfileUnsupported, match=expected):
        registry.resolve(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://alexrivera.substack.com/about",
        "https://speakerdeck.com/alexrivera",
        "https://alexrivera.notion.site/portfolio",
        "https://pypi.org/user/alexrivera",
        "https://alexrivera.com",
    ],
)
def test_server_rendered_public_pages_fall_back_to_the_portfolio_reader(url: str) -> None:
    assert default_declared_profile_registry().resolve(url).platform == "portfolio"


def test_no_domain_is_both_blocked_and_owned_by_a_connector() -> None:
    """A host must resolve to exactly one outcome, or routing is ambiguous."""

    blocked = {domain for domain, _ in BLOCKED_PLATFORMS}
    assert not blocked & set(API_PLATFORM_DOMAINS)


def test_every_blocked_platform_explains_itself_and_keeps_the_link() -> None:
    for domain, reason in BLOCKED_PLATFORMS:
        assert reason.endswith("the link stays on your record as evidence."), domain
        assert len(reason) > 60, domain


def test_no_duplicate_blocked_domains() -> None:
    domains = [domain for domain, _ in BLOCKED_PLATFORMS]
    assert len(domains) == len(set(domains))
