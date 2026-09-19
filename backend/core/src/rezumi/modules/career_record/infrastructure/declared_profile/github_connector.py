"""GitHub public profile connector using the documented REST API."""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchFailed,
    DeclaredProfileFetchResult,
    hostname,
    normalize_declared_profile_url,
    path_segments,
)

_GITHUB_USER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_GITHUB_WEB_HOSTS = frozenset({"github.com", "gist.github.com"})
_SMART_APOSTROPHES = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "`": "'",
    }
)
# Site routes that look exactly like a username in a URL path. Treating one as
# a profile produces a confusing "profile was not found" instead of routing the
# link to the generic fallback.
_RESERVED_PATHS = frozenset(
    {
        "about",
        "apps",
        "collections",
        "contact",
        "customer-stories",
        "dashboard",
        "enterprise",
        "events",
        "explore",
        "features",
        "issues",
        "join",
        "login",
        "marketplace",
        "new",
        "notifications",
        "orgs",
        "organizations",
        "pricing",
        "pulls",
        "readme",
        "search",
        "security",
        "settings",
        "site",
        "sponsors",
        "topics",
        "trending",
        "users",
    }
)
# Second path segments that begin a repository sub-route, not a repo slug.
_REPO_ROUTE_MARKERS = frozenset(
    {
        "blob",
        "commit",
        "commits",
        "compare",
        "discussions",
        "graphs",
        "issues",
        "labels",
        "milestones",
        "network",
        "projects",
        "pull",
        "pulls",
        "pulse",
        "releases",
        "security",
        "settings",
        "stargazers",
        "tags",
        "tree",
        "wiki",
    }
)
_MAX_REPOS = 5
_MAX_TOPICS = 5
_TIMEOUT = 8.0


class GithubDeclaredProfileConnector:
    platform = "github"

    def supports(self, url: str) -> bool:
        return _github_target(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        target = _github_target(normalized)
        if target is None:
            raise DeclaredProfileFetchFailed("GitHub profile URL is not supported")
        username, repo_name = target
        return await asyncio.to_thread(self._fetch_sync, normalized, username, repo_name)

    def _fetch_sync(
        self,
        profile_url: str,
        username: str,
        repo_name: str | None,
    ) -> DeclaredProfileFetchResult:
        user = self._get_json(f"https://api.github.com/users/{username}")
        now = datetime.now(tz=UTC)
        achievements: list[DeclaredProfileAchievement] = []
        seen_repo_urls: set[str] = set()

        name = _normalize_public_text(str(user.get("name") or username))
        profile_html_url = str(user.get("html_url") or f"https://github.com/{username}")
        profile_achievements = self._profile_achievements(
            user,
            name=name,
            profile_html_url=profile_html_url,
        )

        if repo_name is not None:
            pinned = self._repo_achievement(username, repo_name)
            if pinned is not None:
                achievements.append(pinned)
                seen_repo_urls.add(pinned.source_url.casefold())
            else:
                achievements.extend(profile_achievements)
        else:
            achievements.extend(profile_achievements)
            repos = self._get_json(
                f"https://api.github.com/users/{username}/repos"
                "?sort=stars&direction=desc&per_page=30&type=owner"
            )
            if isinstance(repos, list):
                repo_limit = len(profile_achievements) + _MAX_REPOS
                for repo in repos:
                    if len(achievements) >= repo_limit:
                        break
                    achievement = self._achievement_from_repo(repo, seen_repo_urls)
                    if achievement is None:
                        continue
                    achievements.append(achievement)
                    seen_repo_urls.add(achievement.source_url.casefold())

        if not achievements:
            raise DeclaredProfileFetchFailed("GitHub profile did not expose public achievements")

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=now,
            achievements=tuple(achievements),
        )

    def _profile_achievements(
        self,
        user: dict[str, Any],
        *,
        name: str,
        profile_html_url: str,
    ) -> list[DeclaredProfileAchievement]:
        achievements: list[DeclaredProfileAchievement] = []
        bio = _normalize_public_text(str(user.get("bio") or ""))
        if bio and not _is_role_tagline(bio):
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} on GitHub",
                    statement=bio,
                    source_url=profile_html_url,
                    excerpt=bio[:500],
                )
            )

        location = _normalize_public_text(str(user.get("location") or ""))
        if location:
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} — GitHub location",
                    statement=location,
                    source_url=profile_html_url,
                    excerpt=location[:500],
                )
            )

        company = _normalize_public_text(str(user.get("company") or ""))
        if company:
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} — GitHub company",
                    statement=company,
                    source_url=profile_html_url,
                    excerpt=company[:500],
                )
            )

        blog = _normalize_public_text(str(user.get("blog") or ""))
        if blog:
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} — GitHub website",
                    statement=blog,
                    source_url=profile_html_url,
                    excerpt=blog[:500],
                )
            )
        return achievements

    def _repo_achievement(
        self,
        username: str,
        repo_name: str,
    ) -> DeclaredProfileAchievement | None:
        try:
            repo = self._get_json(f"https://api.github.com/repos/{username}/{repo_name}")
        except DeclaredProfileFetchFailed:
            return None
        if not isinstance(repo, dict):
            return None
        return self._achievement_from_repo(repo, set(), pinned=True)

    def _achievement_from_repo(
        self,
        repo: dict[str, Any],
        seen_repo_urls: set[str],
        *,
        pinned: bool = False,
    ) -> DeclaredProfileAchievement | None:
        if not pinned and (repo.get("fork") or repo.get("archived")):
            return None
        repo_name = str(repo.get("name") or "").strip()
        if not repo_name:
            return None
        html_url = str(repo.get("html_url") or "").strip()
        if html_url and html_url.casefold() in seen_repo_urls:
            return None
        description = _normalize_public_text(str(repo.get("description") or ""))
        language = _normalize_public_text(str(repo.get("language") or ""))
        stars = int(repo.get("stargazers_count") or 0)
        owner_login = str((repo.get("owner") or {}).get("login") or "").strip()
        topics = [
            _normalize_public_text(str(topic))
            for topic in (repo.get("topics") or [])
            if str(topic).strip()
        ]
        if not pinned and not description and stars == 0:
            return None
        parts = [description] if description else []
        if language:
            parts.append(f"Primary language: {language}.")
        if stars > 0:
            parts.append(f"{stars} public stars.")
        if topics:
            parts.append(f"Topics: {', '.join(topics[:_MAX_TOPICS])}.")
        statement = " ".join(parts) or f"Public repository {repo_name}."
        title = f"{owner_login}/{repo_name}" if owner_login else repo_name
        return DeclaredProfileAchievement(
            title=title,
            statement=statement,
            source_url=html_url or f"https://github.com/{repo_name}",
            excerpt=statement[:500],
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed GitHub API host
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(200_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("GitHub profile was not found") from exc
            if exc.code in {403, 429}:
                raise DeclaredProfileFetchFailed(
                    "GitHub is rate-limiting public profile reads right now. Try again later."
                ) from exc
            raise DeclaredProfileFetchFailed("GitHub profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("GitHub profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))


def _github_target(url: str) -> tuple[str, str | None] | None:
    """Return the GitHub account and optional repository named by ``url``."""

    if not _is_github_web_host(hostname(url)):
        return None
    segments = path_segments(url)
    if not segments:
        return None

    if segments[0].casefold() == "users":
        if len(segments) < 2:
            return None
        username = segments[1]
        if username.casefold() in _RESERVED_PATHS:
            return None
        return (username, None) if _GITHUB_USER.match(username) else None

    username = segments[0]
    if username.casefold() in _RESERVED_PATHS:
        return None
    if not _GITHUB_USER.match(username):
        return None

    repo_name = None
    if len(segments) >= 2 and segments[1].casefold() not in _REPO_ROUTE_MARKERS:
        repo_name = segments[1]
    return username, repo_name


def _is_github_web_host(host: str) -> bool:
    normalized = host.casefold().rstrip(".").removeprefix("www.")
    return normalized in _GITHUB_WEB_HOSTS


def _normalize_public_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    return unicodedata.normalize("NFKC", normalized.translate(_SMART_APOSTROPHES))


def _is_role_tagline(value: str) -> bool:
    if "|" not in value:
        return False
    segments = [segment.strip() for segment in value.split("|") if segment.strip()]
    if len(segments) < 2:
        return False
    return all(
        len(segment.split()) <= 5 and not any(char in segment for char in ".!?")
        for segment in segments
    )


def _username(url: str) -> str | None:
    """Return the account a GitHub URL belongs to, profile or repository."""

    target = _github_target(url)
    return target[0] if target is not None else None
