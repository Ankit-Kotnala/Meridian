"""Resolve declared-profile connectors by URL.

Platforms deliberately NOT connected here, checked and excluded for cause —
re-verify before ever revisiting any of these:
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
  profile owner must explicitly authorize a Rezumi OAuth app) — a bigger,
  different-shaped scope than every connector here; deferred, not excluded.
"""

from __future__ import annotations

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileConnector,
    DeclaredProfileUnsupported,
    hostname,
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
from rezumi.modules.career_record.infrastructure.declared_profile.orcid_connector import (
    OrcidDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.portfolio_connector import (
    PortfolioDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.stackoverflow_connector import (
    StackOverflowDeclaredProfileConnector,
)

_LINKEDIN_HOSTS = frozenset({"linkedin.com", "lnkd.in"})


class DeclaredProfileConnectorRegistry:
    def __init__(self, connectors: tuple[DeclaredProfileConnector, ...]) -> None:
        self._connectors = connectors

    def resolve(self, url: str) -> DeclaredProfileConnector:
        normalized = normalize_declared_profile_url(url)
        host = hostname(normalized)
        if host in _LINKEDIN_HOSTS:
            raise DeclaredProfileUnsupported(
                "LinkedIn does not permit automated profile reads. "
                "Add achievements manually or use a public GitHub or portfolio link."
            )
        for connector in self._connectors:
            if connector.supports(normalized):
                return connector
        raise DeclaredProfileUnsupported(
            "This link type is not supported for automatic enrichment yet. "
            "GitHub, GitLab, Bitbucket, Stack Overflow, Codeforces, dev.to, "
            "Credly, public portfolio sites, and example.test fixture links "
            "are supported."
        )


def default_declared_profile_registry(
    *, orcid_enabled: bool = False
) -> DeclaredProfileConnectorRegistry:
    connectors: tuple[DeclaredProfileConnector, ...] = (
        FakeDeclaredProfileConnector(),
        GithubDeclaredProfileConnector(),
        GitlabDeclaredProfileConnector(),
        BitbucketDeclaredProfileConnector(),
        StackOverflowDeclaredProfileConnector(),
        CodeforcesDeclaredProfileConnector(),
        DevToDeclaredProfileConnector(),
        CredlyDeclaredProfileConnector(),
    )
    if orcid_enabled:
        connectors = (*connectors, OrcidDeclaredProfileConnector())
    return DeclaredProfileConnectorRegistry((*connectors, PortfolioDeclaredProfileConnector()))
