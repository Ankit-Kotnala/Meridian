"""Stack Overflow public profile connector using the Stack Exchange API.

Stack Exchange's API Terms of Use permit third-party reads of public data on
the condition that Stack Exchange is visibly credited as the content source
wherever that data is shown — the achievement statement built here always
includes that attribution text, not just this comment.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
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
    hostname,
    normalize_declared_profile_url,
)

# Profile URLs look like stackoverflow.com/users/12345/some-display-name.
_SO_USER = re.compile(r"^users/(?P<id>[0-9]{1,20})(?:/.*)?$")
_TIMEOUT = 8.0
_ATTRIBUTION = "Powered by Stack Exchange."


class StackOverflowDeclaredProfileConnector:
    """Reads a user's public Stack Overflow reputation and badges."""

    platform = "stackoverflow"

    def supports(self, url: str) -> bool:
        normalized = normalize_declared_profile_url(url)
        if hostname(normalized) != "stackoverflow.com":
            return False
        path = urlsplit(normalized).path.strip("/")
        return _SO_USER.match(path) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        path = urlsplit(normalized).path.strip("/")
        match = _SO_USER.match(path)
        if match is None:
            raise DeclaredProfileFetchFailed("Stack Overflow profile URL is not supported")
        user_id = match.group("id")
        return await asyncio.to_thread(self._fetch_sync, normalized, user_id)

    def _fetch_sync(self, profile_url: str, user_id: str) -> DeclaredProfileFetchResult:
        payload = self._get_json(
            f"https://api.stackexchange.com/2.3/users/{user_id}?site=stackoverflow"
        )
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise DeclaredProfileFetchFailed("Stack Overflow profile was not found")
        user = items[0]

        display_name = str(user.get("display_name") or "Stack Overflow user").strip()
        reputation = int(user.get("reputation") or 0)
        badges = user.get("badge_counts") if isinstance(user.get("badge_counts"), dict) else {}
        gold = int((badges or {}).get("gold") or 0)
        silver = int((badges or {}).get("silver") or 0)
        bronze = int((badges or {}).get("bronze") or 0)

        statement = (
            f"{reputation} reputation, {gold} gold / {silver} silver / {bronze} bronze "
            f"badges. {_ATTRIBUTION}"
        )
        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=(
                DeclaredProfileAchievement(
                    title=f"{display_name} on Stack Overflow",
                    statement=statement,
                    source_url=profile_url,
                    excerpt=statement[:500],
                ),
            ),
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed Stack Exchange API host
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                raw = response.read(200_000)
            # The Stack Exchange API gzip-compresses every response body
            # regardless of what Accept-Encoding was sent, so always try to
            # decompress and fall back to the raw bytes if it wasn't gzipped.
            with contextlib.suppress(gzip.BadGzipFile):
                raw = gzip.decompress(raw)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed(
                    "Stack Overflow profile was not found"
                ) from exc
            raise DeclaredProfileFetchFailed(
                "Stack Overflow profile could not be read"
            ) from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError, gzip.BadGzipFile) as exc:
            raise DeclaredProfileFetchFailed("Stack Overflow profile could not be read") from exc
        return json.loads(raw.decode("utf-8"))
