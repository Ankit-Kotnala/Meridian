"""Resolve declared-profile connectors by URL."""

from __future__ import annotations

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileConnector,
    DeclaredProfileUnsupported,
    hostname,
    normalize_declared_profile_url,
)
from rezumi.modules.career_record.infrastructure.declared_profile.credly_connector import (
    CredlyDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.fake_connector import (
    FakeDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.github_connector import (
    GithubDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.portfolio_connector import (
    PortfolioDeclaredProfileConnector,
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
            "GitHub public profiles, public portfolio sites, and example.test "
            "fixture links are supported."
        )


def default_declared_profile_registry() -> DeclaredProfileConnectorRegistry:
    return DeclaredProfileConnectorRegistry(
        (
            FakeDeclaredProfileConnector(),
            GithubDeclaredProfileConnector(),
            CredlyDeclaredProfileConnector(),
            PortfolioDeclaredProfileConnector(),
        )
    )
