"""Resume link extraction, normalization, and connector routing."""

from hashlib import sha256
from uuid import uuid4

import pytest

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileUnsupported,
)
from rezumi.modules.career_record.domain.errors import CareerRecordValidationError
from rezumi.modules.career_record.domain.semantic_import import normalize_semantic_url
from rezumi.modules.career_record.infrastructure.declared_profile.portfolio_connector import (
    PortfolioDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.registry import (
    default_declared_profile_registry,
)
from rezumi.modules.career_record.infrastructure.declared_profile.safe_http import (
    SafeHttpPage,
    _TextExtractor,
)
from rezumi.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    SectionKind,
    SemanticEntityKind,
    SemanticFieldType,
    SourceSpan,
)
from rezumi.modules.resume_health.infrastructure.semantic_parser import (
    LocalResumeParserProvider,
)

# --- Resume-side extraction ------------------------------------------------


def _resume(contact_text: str, project_text: str | None = None) -> CanonicalResume:
    sections = [
        CanonicalSection(
            id=uuid4(),
            kind=SectionKind.CONTACT,
            title="Contact",
            confidence_basis_points=9_000,
            blocks=(
                CanonicalBlock(
                    id=uuid4(),
                    kind=BlockKind.PARAGRAPH,
                    text=contact_text,
                    confidence_basis_points=9_000,
                    spans=(SourceSpan(1, 0, len(contact_text)),),
                ),
            ),
        )
    ]
    if project_text is not None:
        sections.append(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.PROJECTS,
                title="Projects",
                confidence_basis_points=9_000,
                blocks=(
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.PARAGRAPH,
                        text=project_text,
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 500, 500 + len(project_text)),),
                    ),
                ),
            )
        )
    return CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=tuple(sections),
        warnings=(),
    )


async def _links(contact_text: str, project_text: str | None = None) -> dict[str, list[str]]:
    semantics = await LocalResumeParserProvider().parse(
        uuid4(), _resume(contact_text, project_text), sha256(b"fictional").hexdigest()
    )
    found: dict[str, list[str]] = {}
    for entity in semantics.entities:
        found[entity.kind.value] = [
            field.value for field in entity.fields if field.field_type is SemanticFieldType.URL
        ]
    return found


@pytest.mark.asyncio
async def test_contact_links_cover_every_supported_platform_without_a_scheme() -> None:
    contact = (
        "Alex Rivera | alex@example.test | github.com/alex-rivera | "
        "gitlab.com/alex | stackoverflow.com/users/12345/alex | "
        "credly.com/users/alex | dev.to/alex | de.linkedin.com/in/alex"
    )

    links = await _links(contact)

    assert links["contact"] == [
        "github.com/alex-rivera",
        "gitlab.com/alex",
        "stackoverflow.com/users/12345/alex",
        "credly.com/users/alex",
        "dev.to/alex",
        "de.linkedin.com/in/alex",
    ]


@pytest.mark.asyncio
async def test_contact_links_drop_wrapping_and_sentence_punctuation() -> None:
    contact = "Alex Rivera. Portfolio (github.com/alex-rivera). See <https://alex.dev>."

    links = await _links(contact)

    assert links["contact"] == ["github.com/alex-rivera", "https://alex.dev"]


@pytest.mark.asyncio
async def test_prose_technology_names_are_not_read_as_links() -> None:
    links = await _links("Alex Rivera | alex@example.test | Node.js, React.js, scikit-learn")

    assert links["contact"] == []


@pytest.mark.asyncio
async def test_project_link_becomes_its_own_field_and_leaves_the_date_alone() -> None:
    links = await _links(
        "Alex Rivera | alex@example.test",
        "Rezumi | github.com/alex/rezumi-2024 | 2023",
    )

    assert links["project"] == ["github.com/alex/rezumi-2024"]
    semantics = await LocalResumeParserProvider().parse(
        uuid4(),
        _resume("Alex Rivera | alex@example.test", "Rezumi | github.com/alex/rezumi-2024 | 2023"),
        sha256(b"fictional").hexdigest(),
    )
    project = next(
        entity for entity in semantics.entities if entity.kind is SemanticEntityKind.PROJECT
    )
    dates = [field.value for field in project.fields if field.field_type is SemanticFieldType.DATE]
    names = [field.value for field in project.fields if field.name == "name"]
    # "2024" inside the URL path must not be mistaken for the project's date,
    # and the URL must not be glued onto the project name.
    assert dates == ["2023"]
    assert names == ["Rezumi"]


# --- Normalization ---------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("github.com/alex", "https://github.com/alex"),
        ("www.github.com/alex", "https://www.github.com/alex"),
        ("(github.com/alex).", "https://github.com/alex"),
        ("<https://alex.dev>", "https://alex.dev"),
        ("HTTPS://GitHub.com:443//Alex/", "https://github.com/Alex"),
        ("https://alex.dev./", "https://alex.dev/"),
    ],
)
def test_normalize_semantic_url_canonicalizes(raw: str, expected: str) -> None:
    assert normalize_semantic_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["mailto:alex@example.test", "javascript:alert(1)", "file:///etc/passwd", "alex"],
)
def test_normalize_semantic_url_rejects_non_web_links(raw: str) -> None:
    with pytest.raises(CareerRecordValidationError):
        normalize_semantic_url(raw)


def test_normalize_semantic_url_rejects_embedded_credentials() -> None:
    with pytest.raises(CareerRecordValidationError):
        normalize_semantic_url("https://user:secret@alex.dev/profile")


# --- Connector routing -----------------------------------------------------


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://github.com/alex", "github"),
        ("https://github.com/alex/rezumi", "github"),
        ("https://gist.github.com/alex", "github"),
        ("https://GitHub.com:443/Alex/", "github"),
        ("https://www.gitlab.com/alex/pipeline-kit", "gitlab"),
        ("https://stackoverflow.com/users/12345/alex-rivera", "stackexchange"),
        ("https://quant.stackexchange.com/users/848/bob", "stackexchange"),
        ("https://law.stackexchange.com/users/1/alex", "stackexchange"),
        ("https://mathoverflow.net/users/1/alex", "stackexchange"),
        ("https://orcid.org/0000-0003-1613-5981", "openalex"),
        ("https://openalex.org/A5048491430", "openalex"),
        ("https://www.credly.com/users/alex/badges", "credly"),
        ("https://dev.to/alex/a-post-slug", "devto"),
        ("https://alex.dev/about", "portfolio"),
        ("https://alex.github.io", "portfolio"),
    ],
)
def test_registry_routes_real_resume_link_shapes(url: str, platform: str) -> None:
    assert default_declared_profile_registry().resolve(url).platform == platform


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://de.linkedin.com/in/alex", "LinkedIn"),
        ("https://www.linkedin.com/in/alex", "LinkedIn"),
        ("https://lnkd.in/abc123", "LinkedIn"),
        ("https://leetcode.com/alex", "LeetCode"),
        ("https://www.hackerrank.com/alex", "HackerRank"),
        ("https://kaggle.com/alex", "Kaggle"),
        ("https://medium.com/@alex", "Medium"),
        ("https://m.facebook.com/alex", "Facebook"),
        ("https://x.com/alex", "X"),
    ],
)
def test_registry_refuses_platforms_excluded_for_cause(url: str, expected: str) -> None:
    """Subdomains included: these must never reach the HTML scraping fallback."""

    registry = default_declared_profile_registry()
    with pytest.raises(DeclaredProfileUnsupported, match=expected):
        registry.resolve(url)


def test_portfolio_connector_never_claims_a_platform_or_blocked_host() -> None:
    connector = PortfolioDeclaredProfileConnector()
    for url in (
        "https://gist.github.com/alex",
        "https://de.linkedin.com/in/alex",
        "https://leetcode.com/alex",
        "https://www.medium.com/@alex",
        "https://stackoverflow.com/users/1/alex",
    ):
        assert not connector.supports(url)
    assert connector.supports("https://alex.dev")


def test_credly_badge_permalink_is_not_read_as_an_account() -> None:
    registry = default_declared_profile_registry()
    with pytest.raises(DeclaredProfileUnsupported):
        registry.resolve("https://www.credly.com/badges/6f1a0c2e-0000-4000-8000-000000000000")


# --- Portfolio HTML extraction ---------------------------------------------


class _StubFetcher:
    def __init__(self, page: SafeHttpPage) -> None:
        self._page = page

    async def fetch(self, url: str) -> SafeHttpPage:
        _ = url
        return self._page


@pytest.mark.asyncio
async def test_portfolio_prefers_the_page_summary_and_skips_navigation() -> None:
    page = SafeHttpPage(
        final_url="https://alex.dev/",
        title="Alex Rivera",
        text=(
            "Home About Projects Contact\n"
            "Selected work\n"
            "Rebuilt the billing pipeline for a fictional insurer\n"
            "This site uses cookies to improve your experience\n"
            "Copyright 2026 Alex Rivera"
        ),
        description="Staff engineer building payment and billing systems.",
        headings=("Selected work",),
    )

    result = await PortfolioDeclaredProfileConnector(fetcher=_StubFetcher(page)).fetch(
        "https://alex.dev/"
    )

    titles = [item.title for item in result.achievements]
    assert titles[0] == "Alex Rivera"
    assert result.achievements[0].statement == (
        "Staff engineer building payment and billing systems."
    )
    assert "Selected work" in titles
    assert not any("cookies" in item.statement for item in result.achievements)
    assert not any("Copyright" in item.title for item in result.achievements)
    assert "Home About Projects Contact" not in titles


def test_text_extractor_reads_metadata_and_drops_chrome() -> None:
    parser = _TextExtractor()
    parser.feed(
        "<html><head><title>Alex Rivera</title>"
        '<meta name="description" content="Staff engineer building billing systems.">'
        "</head><body>"
        "<nav><a>Home</a><a>Contact</a></nav>"
        "<h2>Selected work</h2><p>Rebuilt the billing pipeline.</p>"
        "<script>var tracked = 1;</script>"
        "<footer>Copyright 2026</footer>"
        "</body></html>"
    )
    parser.close()

    assert parser.title() == "Alex Rivera"
    assert parser.description() == "Staff engineer building billing systems."
    assert parser.headings() == ("Selected work",)
    assert "Rebuilt the billing pipeline." in parser.text()
    for chrome in ("Home", "Contact", "tracked", "Copyright"):
        assert chrome not in parser.text()
