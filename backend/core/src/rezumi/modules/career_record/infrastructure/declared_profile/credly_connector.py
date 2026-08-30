"""Credly public badge connector using Credly's documented public JSON feed."""

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

_CREDLY_USER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MAX_BADGES = 8
_TIMEOUT = 8.0


class CredlyDeclaredProfileConnector:
    """Reads a user's public Credly badge feed (`credly.com/users/<slug>`)."""

    platform = "credly"

    def supports(self, url: str) -> bool:
        return _user_slug(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        slug = _user_slug(normalized)
        if slug is None:
            raise DeclaredProfileFetchFailed("Credly profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, slug)

    def _fetch_sync(self, profile_url: str, slug: str) -> DeclaredProfileFetchResult:
        payload = self._get_json(f"https://www.credly.com/users/{slug}/badges.json")
        badges = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(badges, list):
            raise DeclaredProfileFetchFailed("Credly profile did not expose public badges")

        achievements: list[DeclaredProfileAchievement] = []
        for badge in badges[:_MAX_BADGES]:
            if not isinstance(badge, dict):
                continue
            template = badge.get("badge_template")
            name = str((template or {}).get("name") or "").strip()
            if not name:
                continue
            issuer_entities = ((template or {}).get("issuer") or {}).get("entities")
            issuer = ""
            if isinstance(issuer_entities, list) and issuer_entities:
                first = issuer_entities[0]
                if isinstance(first, dict):
                    issuer = str((first.get("entity") or {}).get("name") or "").strip()
            issued_at = str(badge.get("issued_at") or "").strip()
            badge_url = str(badge.get("public_url") or profile_url)
            parts = [p for p in (f"Issued by {issuer}." if issuer else "", issued_at) if p]
            statement = " ".join(parts) or f"Public credential: {name}."
            achievements.append(
                DeclaredProfileAchievement(
                    title=name,
                    statement=statement,
                    source_url=badge_url,
                    excerpt=statement[:500],
                )
            )

        if not achievements:
            raise DeclaredProfileFetchFailed("Credly profile did not expose public badges")

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=tuple(achievements),
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed Credly API host
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                body = response.read(200_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("Credly profile was not found") from exc
            raise DeclaredProfileFetchFailed("Credly profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("Credly profile could not be read") from exc
        return json.loads(body.decode("utf-8"))


def _user_slug(url: str) -> str | None:
    """Return the Credly account slug a badge-feed URL names.

    Only "/users/<slug>" identifies an account. A single-badge permalink
    ("/badges/<uuid>") is a different resource with a different feed, and
    feeding its id to the user badge endpoint reads someone else's page or
    nothing at all -- it is left unsupported rather than silently mis-fetched.
    """

    if not host_matches(hostname(url), "credly.com"):
        return None
    segments = path_segments(url)
    if len(segments) < 2 or segments[0].casefold() != "users":
        return None
    return segments[1] if _CREDLY_USER.match(segments[1]) else None
