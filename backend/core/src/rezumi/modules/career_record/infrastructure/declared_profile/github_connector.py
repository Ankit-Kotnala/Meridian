"""GitHub public profile connector using the documented REST API."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchFailed,
    DeclaredProfileFetchResult,
    host_matches,
    hostname,
    normalize_declared_profile_url,
    path_segments,
)

_GITHUB_USER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
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
    }
)
_MAX_REPOS = 5
_TIMEOUT = 8.0


class GithubDeclaredProfileConnector:
    platform = "github"

    def supports(self, url: str) -> bool:
        return _username(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        username = _username(normalized)
        if username is None:
            raise DeclaredProfileFetchFailed("GitHub profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, username)

    def _fetch_sync(self, profile_url: str, username: str) -> DeclaredProfileFetchResult:
        user = self._get_json(f"https://api.github.com/users/{username}")
        repos = self._get_json(
            f"https://api.github.com/users/{username}/repos"
            "?sort=updated&direction=desc&per_page=5&type=owner"
        )
        now = datetime.now(tz=UTC)
        achievements: list[DeclaredProfileAchievement] = []

        bio = str(user.get("bio") or "").strip()
        name = str(user.get("name") or username).strip()
        public_repos = int(user.get("public_repos") or 0)
        if bio or public_repos > 0:
            statement = bio or f"Public GitHub profile with {public_repos} repositories."
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} on GitHub",
                    statement=statement,
                    source_url=profile_url,
                    excerpt=statement[:500],
                )
            )

        if isinstance(repos, list):
            for repo in repos[:_MAX_REPOS]:
                if not isinstance(repo, dict):
                    continue
                repo_name = str(repo.get("name") or "").strip()
                if not repo_name:
                    continue
                description = str(repo.get("description") or "").strip()
                language = str(repo.get("language") or "").strip()
                stars = int(repo.get("stargazers_count") or 0)
                html_url = str(repo.get("html_url") or f"{profile_url}/{repo_name}")
                parts = [description] if description else []
                if language:
                    parts.append(f"Primary language: {language}.")
                if stars > 0:
                    parts.append(f"{stars} public stars.")
                statement = " ".join(parts) or f"Public repository {repo_name}."
                achievements.append(
                    DeclaredProfileAchievement(
                        title=repo_name,
                        statement=statement,
                        source_url=html_url,
                        excerpt=statement[:500],
                    )
                )

        if not achievements:
            raise DeclaredProfileFetchFailed("GitHub profile did not expose public achievements")

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=now,
            achievements=tuple(achievements),
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


def _username(url: str) -> str | None:
    """Return the account a GitHub URL belongs to, profile or repository.

    Resumes cite the work, not the profile page: "github.com/alex/rezumi" is at
    least as common as "github.com/alex", and gist links are equally valid
    evidence of the same account. Both resolve to that account's public
    profile rather than being rejected as unsupported.
    """

    # `alex.github.io` is a published site rather than an API-backed profile,
    # and is left to the portfolio connector: it is not a github.com host.
    if not host_matches(hostname(url), "github.com"):
        return None
    segments = path_segments(url)
    if not segments:
        return None
    candidate = segments[0]
    if candidate.casefold() in _RESERVED_PATHS:
        return None
    return candidate if _GITHUB_USER.match(candidate) else None
