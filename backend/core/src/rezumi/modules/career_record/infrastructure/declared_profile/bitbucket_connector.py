"""Bitbucket public profile connector using the documented Cloud REST API.

Bitbucket's Acceptable Use Policy page was unreachable during review (404 on
every attempt) — the public API itself works and returns only the fields the
user has made public (private-profile fields are simply omitted by
Bitbucket, not exposed here), but re-verify that policy text once reachable
before treating this as fully cleared.

Live-verification gap: unlike the other new connectors in this module (all
confirmed against a real public account), this one could not be proven
against live data — every individual-user handle tried (several real,
findable people) returned 404, and Bitbucket has deprecated the unauthenticated
bulk `GET /2.0/repositories` listing (`410 Gone`) that would otherwise help
find one. The endpoints used here (`/2.0/users/{username}`,
`/2.0/repositories/{username}`) are still current per Bitbucket's own API
docs, and the connector's unit tests exercise realistic mocked response
shapes for both, but treat this one as unverified-against-live-data until
someone confirms it against a real account.
"""

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

_BITBUCKET_USER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_RESERVED_PATHS = frozenset(
    {"account", "dashboard", "product", "repo", "search", "site", "workspace"}
)
_MAX_REPOS = 5
_TIMEOUT = 8.0


class BitbucketDeclaredProfileConnector:
    """Reads a user's public Bitbucket profile (`bitbucket.org/<user>`)."""

    platform = "bitbucket"

    def supports(self, url: str) -> bool:
        return _username(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        username = _username(normalized)
        if username is None:
            raise DeclaredProfileFetchFailed("Bitbucket profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, username)

    def _fetch_sync(self, profile_url: str, username: str) -> DeclaredProfileFetchResult:
        user = self._get_json(f"https://api.bitbucket.org/2.0/users/{username}")
        repos = self._get_json(
            f"https://api.bitbucket.org/2.0/repositories/{username}?pagelen=5&sort=-updated_on"
        )

        display_name = str(user.get("display_name") or username).strip()
        achievements: list[DeclaredProfileAchievement] = []

        repo_values = repos.get("values") if isinstance(repos, dict) else None
        repo_list = repo_values if isinstance(repo_values, list) else []
        has_more = isinstance(repos, dict) and bool(repos.get("next"))
        repo_count_label = f"{len(repo_list)}{'+' if has_more else ''}"

        if repo_list:
            statement = f"Public Bitbucket profile with {repo_count_label} public repositories."
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{display_name} on Bitbucket",
                    statement=statement,
                    source_url=profile_url,
                    excerpt=statement[:500],
                )
            )

        for repo in repo_list[:_MAX_REPOS]:
            if not isinstance(repo, dict):
                continue
            repo_name = str(repo.get("name") or "").strip()
            if not repo_name:
                continue
            description = str(repo.get("description") or "").strip()
            language = str(repo.get("language") or "").strip()
            links = repo.get("links") if isinstance(repo.get("links"), dict) else {}
            html_link = links.get("html") if isinstance(links, dict) else None
            html_link = html_link if isinstance(html_link, dict) else {}
            repo_url = str(html_link.get("href") or profile_url)
            parts = [description] if description else []
            if language:
                parts.append(f"Primary language: {language}.")
            statement = " ".join(parts) or f"Public repository {repo_name}."
            achievements.append(
                DeclaredProfileAchievement(
                    title=repo_name,
                    statement=statement,
                    source_url=repo_url,
                    excerpt=statement[:500],
                )
            )

        if not achievements:
            raise DeclaredProfileFetchFailed("Bitbucket profile did not expose public achievements")

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=tuple(achievements),
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed Bitbucket API host
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(200_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("Bitbucket profile was not found") from exc
            raise DeclaredProfileFetchFailed("Bitbucket profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("Bitbucket profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))


def _username(url: str) -> str | None:
    """Return the Bitbucket workspace/account a profile or repo URL names."""

    if not host_matches(hostname(url), "bitbucket.org"):
        return None
    segments = path_segments(url)
    if not segments:
        return None
    candidate = segments[0]
    if candidate.casefold() in _RESERVED_PATHS:
        return None
    return candidate if _BITBUCKET_USER.match(candidate) else None
