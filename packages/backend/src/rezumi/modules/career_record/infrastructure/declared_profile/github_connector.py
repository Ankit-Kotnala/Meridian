"""GitHub public profile connector using the documented REST API."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchFailed,
    DeclaredProfileFetchResult,
    normalize_declared_profile_url,
)

_GITHUB_USER = re.compile(
    r"^github\.com/(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)/?$"
)
_MAX_REPOS = 5
_TIMEOUT = 8.0


class GithubDeclaredProfileConnector:
    platform = "github"

    def supports(self, url: str) -> bool:
        normalized = normalize_declared_profile_url(url)
        path = urlsplit(normalized).path.strip("/")
        host = (urlsplit(normalized).hostname or "").casefold().removeprefix("www.")
        if host != "github.com":
            return False
        return _GITHUB_USER.match(f"github.com/{path}") is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        match = _GITHUB_USER.match(f"github.com/{urlsplit(normalized).path.strip('/')}/")
        if match is None:
            raise DeclaredProfileFetchFailed("GitHub profile URL is not supported")
        username = match.group("user")
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
            raise DeclaredProfileFetchFailed("GitHub profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("GitHub profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))
