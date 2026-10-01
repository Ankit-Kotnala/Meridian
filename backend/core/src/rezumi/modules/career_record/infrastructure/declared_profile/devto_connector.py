"""dev.to (Forem) public profile connector using the documented public API."""

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
from rezumi.modules.career_record.infrastructure.declared_profile.normalization import (
    positive_public_int,
)

_DEVTO_USER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
_RESERVED_PATHS = frozenset(
    {"about", "api", "enter", "latest", "search", "settings", "signout", "t", "tags", "top"}
)
_MAX_ARTICLES = 10
_TIMEOUT = 8.0


class DevToDeclaredProfileConnector:
    """Reads a user's public dev.to profile summary and article activity."""

    platform = "devto"

    def supports(self, url: str) -> bool:
        return _username(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        username = _username(normalized)
        if username is None:
            raise DeclaredProfileFetchFailed("dev.to profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, username)

    def _fetch_sync(self, profile_url: str, username: str) -> DeclaredProfileFetchResult:
        user = self._get_json(f"https://dev.to/api/users/by_username?url={username}")
        if not isinstance(user, dict) or not user.get("id"):
            raise DeclaredProfileFetchFailed("dev.to profile was not found")

        name = str(user.get("name") or username).strip()
        summary = str(user.get("summary") or "").strip()

        articles = self._get_json(
            f"https://dev.to/api/articles?username={username}&per_page={_MAX_ARTICLES}"
        )
        article_list = articles if isinstance(articles, list) else []
        total_reactions = sum(
            positive_public_int(article.get("positive_reactions_count"))
            for article in article_list
            if isinstance(article, dict)
        )

        parts = [summary] if summary else []
        if article_list:
            has_more = len(article_list) >= _MAX_ARTICLES
            parts.append(
                f"{len(article_list)}{'+' if has_more else ''} public posts, "
                f"{total_reactions} total reactions."
            )
        if not parts:
            raise DeclaredProfileFetchFailed("dev.to profile did not expose public achievements")
        statement = " ".join(parts)

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=(
                DeclaredProfileAchievement(
                    title=f"{name} on dev.to",
                    statement=statement,
                    source_url=profile_url,
                    excerpt=statement[:500],
                ),
            ),
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed dev.to API host
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(500_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("dev.to profile was not found") from exc
            raise DeclaredProfileFetchFailed("dev.to profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("dev.to profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))


def _username(url: str) -> str | None:
    """Return the dev.to author a profile or article URL names.

    Article URLs are "dev.to/<author>/<slug>" — a resume citing a specific
    post still identifies the author whose public activity is being read.
    """

    if not host_matches(hostname(url), "dev.to"):
        return None
    segments = path_segments(url)
    if not segments:
        return None
    candidate = segments[0]
    if candidate.casefold() in _RESERVED_PATHS:
        return None
    return candidate if _DEVTO_USER.match(candidate) else None
