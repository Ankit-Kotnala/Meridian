"""Resolve declared-profile connectors by URL.

Every recognized platform lands in exactly one of three buckets - dedicated
connector, generic HTML fallback, or an explicit refusal carrying its reason.
`platform_policy.py` holds the catalogue and the reasoning per domain; this
module only routes.

Findings behind the engineering exclusions listed there, re-verify before ever
revisiting any of them:
- LinkedIn: the User Agreement forbids automated access to profiles.
- LeetCode: ToS forbids "crawling," "scraping," "spidering"; robots.txt
  disallows /api/ and /graphql for all crawlers; no documented public API.
- HackerRank: no documented public API; robots.txt disallows /rest/ and
  /profile/.
- CodeChef: ToS forbids "spam, phish, farm, pretext, spider, crawl, or
  scrape"; no official public API.
- Kaggle: ToS forbids scraping; no documented endpoint exposes profile
  rank/medals/notebook counts.
- Behance: Adobe has taken the public API offline (every docs URL 404s).
- Medium: API deprecated/archived by Medium itself since March 2023.
- Dribbble: has a public API, but it's OAuth2-authorization-flow only (the
  profile owner must explicitly authorize a Rezumi OAuth app) - a bigger,
  different-shaped scope than every connector here; deferred, not excluded.
- ResearchGate: answers unauthenticated requests with 403.
- Google Scholar: consent- and captcha-walled; terms forbid automated access.

A refusal is a feature, not a gap: the declared link is still stored as
evidence on the career record, and the user writes the achievement themselves
rather than being handed scraped navigation chrome as if it were their work.
"""

from __future__ import annotations

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileConnector,
    DeclaredProfileUnsupported,
    normalize_declared_profile_url,
)
from rezumi.modules.career_record.infrastructure.declared_profile.bitbucket_connector import (
    BitbucketDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.codeforces_connector import (
    CodeforcesDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.credly_connector import (
    CredlyDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.devto_connector import (
    DevToDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.fake_connector import (
    FakeDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.github_connector import (
    GithubDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.gitlab_connector import (
    GitlabDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.openalex_connector import (
    OpenAlexDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.orcid_connector import (
    OrcidDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.platform_policy import (
    UNSUPPORTED_LINK_MESSAGE,
    blocked_platform_reason,
)
from rezumi.modules.career_record.infrastructure.declared_profile.portfolio_connector import (
    PortfolioDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.stackexchange_connector import (
    StackExchangeDeclaredProfileConnector,
)


class DeclaredProfileConnectorRegistry:
    def __init__(self, connectors: tuple[DeclaredProfileConnector, ...]) -> None:
        self._connectors = connectors

    def resolve(self, url: str) -> DeclaredProfileConnector:
        normalized = normalize_declared_profile_url(url)
        reason = blocked_platform_reason(normalized)
        if reason is not None:
            raise DeclaredProfileUnsupported(reason)
        for connector in self._connectors:
            if connector.supports(normalized):
                return connector
        raise DeclaredProfileUnsupported(UNSUPPORTED_LINK_MESSAGE)


def default_declared_profile_registry(
    *,
    github_api_token: str | None = None,
    orcid_enabled: bool = False,
) -> DeclaredProfileConnectorRegistry:
    connectors: tuple[DeclaredProfileConnector, ...] = (
        FakeDeclaredProfileConnector(),
        GithubDeclaredProfileConnector(api_token=github_api_token),
        GitlabDeclaredProfileConnector(),
        BitbucketDeclaredProfileConnector(),
        StackExchangeDeclaredProfileConnector(),
        CodeforcesDeclaredProfileConnector(),
        DevToDeclaredProfileConnector(),
        CredlyDeclaredProfileConnector(),
    )
    if orcid_enabled:
        # ORCID is registered ahead of OpenAlex so that, once cleared, an
        # orcid.org link is read from ORCID itself rather than the CC0 mirror.
        connectors = (*connectors, OrcidDeclaredProfileConnector())
    return DeclaredProfileConnectorRegistry(
        (
            *connectors,
            OpenAlexDeclaredProfileConnector(),
            PortfolioDeclaredProfileConnector(),
        )
    )
