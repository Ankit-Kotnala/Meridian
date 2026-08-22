"""Public personal-site / portfolio HTML connector."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchResult,
    hostname,
    normalize_declared_profile_url,
)
from rezumi.modules.career_record.infrastructure.declared_profile.safe_http import (
    SafeHttpFetcher,
)

_KNOWN_PLATFORM_HOSTS = frozenset(
    {
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "linkedin.com",
        "lnkd.in",
        "example.test",
    }
)
_HEADING = re.compile(
    r"^(?P<title>.{3,120}?)(?:\s*[-–—:]\s*(?P<body>.+))?$",
    re.MULTILINE,
)
_MAX_ACHIEVEMENTS = 8
_EXCERPT = 400


class PortfolioDeclaredProfileConnector:
    platform = "portfolio"

    def __init__(self, fetcher: SafeHttpFetcher | None = None) -> None:
        self._fetcher = fetcher or SafeHttpFetcher()

    def supports(self, url: str) -> bool:
        normalized = normalize_declared_profile_url(url)
        host = hostname(normalized)
        if host in _KNOWN_PLATFORM_HOSTS:
            return False
        return True

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        page = await self._fetcher.fetch(normalized)
        achievements = _extract_achievements(page.text, page.final_url, page.title)
        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=page.final_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=achievements,
        )


def _extract_achievements(
    text: str,
    source_url: str,
    page_title: str | None,
) -> tuple[DeclaredProfileAchievement, ...]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[DeclaredProfileAchievement] = []

    for line in lines:
        if len(line) < 12:
            continue
        if line.casefold().startswith(("copyright", "all rights reserved", "cookie")):
            continue
        match = _HEADING.match(line)
        if match is None:
            continue
        title = match.group("title").strip()
        body = (match.group("body") or title).strip()
        if len(title) < 3:
            continue
        excerpt = body[:_EXCERPT]
        candidates.append(
            DeclaredProfileAchievement(
                title=title[:120],
                statement=body[:500],
                source_url=source_url,
                excerpt=excerpt,
            )
        )
        if len(candidates) >= _MAX_ACHIEVEMENTS:
            break

    if candidates:
        return tuple(candidates)

    host = hostname(source_url)
    title = page_title or f"Public portfolio ({host})"
    excerpt = text[:_EXCERPT]
    return (
        DeclaredProfileAchievement(
            title=title[:120],
            statement=text[:500],
            source_url=source_url,
            excerpt=excerpt,
        ),
    )
