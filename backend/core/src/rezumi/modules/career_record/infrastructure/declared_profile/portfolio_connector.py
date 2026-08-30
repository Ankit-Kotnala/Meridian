"""Public personal-site / portfolio HTML connector."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchResult,
    hostname,
    normalize_declared_profile_url,
)
from rezumi.modules.career_record.infrastructure.declared_profile.platform_policy import (
    blocked_platform_reason,
    is_api_platform_host,
)
from rezumi.modules.career_record.infrastructure.declared_profile.safe_http import (
    SafeHttpFetcher,
    SafeHttpPage,
)

# A content line only becomes an achievement when it reads like a claim: a
# title, a separator, then a body. Requiring whitespace after the separator
# keeps hyphenated words ("e-commerce", "end-to-end") from being split apart.
_TITLE_BODY = re.compile(r"^(?P<title>.{3,120}?)\s*[-:\u2013\u2014\u2022]\s+(?P<body>.{3,})$")
_HAS_LETTER = re.compile(r"[^\W\d_]")
_HAS_LOWERCASE = re.compile(r"[a-z\u00df-\u00ff]")
# Site chrome and legal furniture that appears on almost every personal site.
# Without this filter the first eight "achievements" imported from a portfolio
# are its navigation menu and cookie banner.
_BOILERPLATE_PREFIXES = (
    "copyright",
    "all rights reserved",
    "cookie",
    "privacy policy",
    "terms of",
    "terms and conditions",
    "skip to",
    "back to top",
    "powered by",
    "subscribe",
    "sign in",
    "sign up",
    "log in",
    "menu",
    "read more",
    "loading",
    "javascript is",
    "enable javascript",
)
_BOILERPLATE_CONTAINS = (
    "\u00a9",
    "all rights reserved",
    "uses cookies",
    "accept cookies",
)
_MIN_LINE = 12
_MAX_LINE = 400
_MAX_ACHIEVEMENTS = 8
_EXCERPT = 400


class PortfolioDeclaredProfileConnector:
    platform = "portfolio"

    def __init__(self, fetcher: SafeHttpFetcher | None = None) -> None:
        self._fetcher = fetcher or SafeHttpFetcher()

    def supports(self, url: str) -> bool:
        normalized = normalize_declared_profile_url(url)
        if is_api_platform_host(normalized):
            return False
        return blocked_platform_reason(normalized) is None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        page = await self._fetcher.fetch(normalized)
        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=page.final_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=_extract_achievements(page),
        )


def _extract_achievements(page: SafeHttpPage) -> tuple[DeclaredProfileAchievement, ...]:
    lines = [line.strip() for line in page.text.splitlines() if line.strip()]
    headings = {heading.casefold() for heading in page.headings}
    achievements: list[DeclaredProfileAchievement] = []
    seen: set[str] = set()

    def add(title: str, statement: str) -> None:
        title = title.strip()[:120]
        statement = statement.strip()
        key = title.casefold()
        if not title or not statement or key in seen:
            return
        if _HAS_LETTER.search(title) is None:
            return
        seen.add(key)
        achievements.append(
            DeclaredProfileAchievement(
                title=title,
                statement=statement[:500],
                source_url=page.final_url,
                excerpt=statement[:_EXCERPT],
            )
        )

    # The page's own summary is the most reliable single statement a personal
    # site publishes about itself, so it leads when the author provided one.
    if page.description:
        add(page.title or f"Public portfolio ({hostname(page.final_url)})", page.description)

    for index, line in enumerate(lines):
        if len(achievements) >= _MAX_ACHIEVEMENTS:
            break
        if _is_boilerplate(line):
            continue
        if line.casefold() in headings:
            body = _body_after(lines, index, headings)
            if body is not None:
                add(line, body)
            continue
        match = _TITLE_BODY.match(line)
        if match is not None:
            add(match.group("title"), match.group("body"))
            continue
        if _is_prose(line):
            add(_leading_clause(line), line)

    if achievements:
        return tuple(achievements)

    host = hostname(page.final_url)
    title = page.title or f"Public portfolio ({host})"
    statement = page.description or page.text
    return (
        DeclaredProfileAchievement(
            title=title[:120],
            statement=statement[:500],
            source_url=page.final_url,
            excerpt=statement[:_EXCERPT],
        ),
    )


def _is_boilerplate(line: str) -> bool:
    if len(line) < _MIN_LINE or len(line) > _MAX_LINE:
        return True
    normalized = line.casefold()
    if normalized.startswith(_BOILERPLATE_PREFIXES):
        return True
    return any(token in normalized for token in _BOILERPLATE_CONTAINS)


def _is_prose(line: str) -> bool:
    """Whether a separator-less line reads as a sentence rather than a menu.

    A navigation strip that survived into the text ("Home About Projects
    Contact") is all title-case labels; a real claim carries at least one
    lower-case connecting word.
    """

    words = line.split()
    if len(words) < 4:
        return False
    return any(_HAS_LOWERCASE.match(word) is not None for word in words[1:])


def _body_after(lines: list[str], index: int, headings: set[str]) -> str | None:
    """Return the first content line under a heading, if the heading has one."""

    for candidate in lines[index + 1 : index + 4]:
        if candidate.casefold() in headings or _is_boilerplate(candidate):
            continue
        return candidate
    return None


def _leading_clause(line: str) -> str:
    """Title a prose line by its first clause, so cards stay scannable."""

    for separator in (". ", "; "):
        head, found, _ = line.partition(separator)
        if found and len(head) >= 3:
            return head
    return line
