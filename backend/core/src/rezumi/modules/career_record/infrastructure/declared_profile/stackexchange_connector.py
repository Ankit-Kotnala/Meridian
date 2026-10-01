"""Stack Exchange network public profile connector.

Stack Exchange's API Terms of Use permit third-party reads of public data on
the condition that Stack Exchange is visibly credited as the content source
wherever that data is shown - the achievement statement built here always
includes that attribution text, not just this comment.

The whole network is covered, not just Stack Overflow, because the network is
where non-engineering expertise is demonstrated publicly: Quantitative Finance,
Law, Economics, Academia, Workplace, Cross Validated, and roughly 170 other
sites all answer the same documented `/2.3/users/{id}` endpoint under a
different `site` parameter. Reading only stackoverflow.com meant a finance or
legal resume citing its author profile got "unsupported link".

Verified against live data for `stackoverflow` and `quant` on 2026-08-30.
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

# Profile URLs look like <site>/users/12345/some-display-name.
_USER_ID = re.compile(r"^[0-9]{1,20}$")
_SITE_LABEL = re.compile(r"^[a-z0-9-]+$")
# Network sites that do not sit under stackexchange.com.
_STANDALONE_SITES = {
    "stackoverflow.com": "stackoverflow",
    "serverfault.com": "serverfault",
    "superuser.com": "superuser",
    "askubuntu.com": "askubuntu",
    "mathoverflow.net": "mathoverflow",
    "stackapps.com": "stackapps",
}
# Localized Stack Overflow sites keep their language prefix in the API key.
_LOCALIZED_STACKOVERFLOW = frozenset({"pt", "es", "ja", "ru"})
_TIMEOUT = 8.0
_ATTRIBUTION = "Powered by Stack Exchange."


class StackExchangeDeclaredProfileConnector:
    """Reads a user's public reputation and badges on any Stack Exchange site."""

    platform = "stackexchange"

    def supports(self, url: str) -> bool:
        return _profile(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        profile = _profile(normalized)
        if profile is None:
            raise DeclaredProfileFetchFailed("Stack Exchange profile URL is not supported")
        site, user_id = profile
        return await asyncio.to_thread(self._fetch_sync, normalized, site, user_id)

    def _fetch_sync(self, profile_url: str, site: str, user_id: str) -> DeclaredProfileFetchResult:
        payload = self._get_json(f"https://api.stackexchange.com/2.3/users/{user_id}?site={site}")
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise DeclaredProfileFetchFailed("Stack Exchange profile was not found")
        user = items[0]

        display_name = str(user.get("display_name") or "Stack Exchange user").strip()
        reputation = positive_public_int(user.get("reputation"))
        badges = user.get("badge_counts") if isinstance(user.get("badge_counts"), dict) else {}
        gold = positive_public_int((badges or {}).get("gold"))
        silver = positive_public_int((badges or {}).get("silver"))
        bronze = positive_public_int((badges or {}).get("bronze"))

        site_name = str(user.get("link") or "").strip()
        site_label = hostname(site_name) if site_name else f"{site}.stackexchange.com"
        statement = (
            f"{reputation} reputation on {site_label}, {gold} gold / {silver} silver / "
            f"{bronze} bronze badges. {_ATTRIBUTION}"
        )
        return DeclaredProfileFetchResult(
            platform="stackoverflow" if site == "stackoverflow" else self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=(
                DeclaredProfileAchievement(
                    title=f"{display_name} on {site_label}",
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
                raise DeclaredProfileFetchFailed("Stack Exchange profile was not found") from exc
            if exc.code in {400, 429}:
                raise DeclaredProfileFetchFailed(
                    "Stack Exchange is throttling public profile reads right now. Try again later."
                ) from exc
            raise DeclaredProfileFetchFailed("Stack Exchange profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError, gzip.BadGzipFile) as exc:
            raise DeclaredProfileFetchFailed("Stack Exchange profile could not be read") from exc
        return json.loads(raw.decode("utf-8"))


def _site_key(host: str) -> str | None:
    """Map a network host to the API's ``site`` parameter.

    Meta sites are excluded: reputation earned discussing the site itself is
    not the professional signal the profile link was cited for.
    """

    normalized = host.casefold().rstrip(".").removeprefix("www.")
    if normalized.startswith("meta."):
        return None
    standalone = _STANDALONE_SITES.get(normalized)
    if standalone is not None:
        return standalone
    if normalized.endswith(".stackoverflow.com"):
        language = normalized.removesuffix(".stackoverflow.com")
        return f"{language}.stackoverflow" if language in _LOCALIZED_STACKOVERFLOW else None
    if host_matches(normalized, "stackexchange.com"):
        label = normalized.removesuffix(".stackexchange.com")
        if label == normalized or not _SITE_LABEL.match(label):
            return None
        return label
    return None


def _profile(url: str) -> tuple[str, str] | None:
    """Return the (site, numeric account id) a Stack Exchange URL names.

    Profile links carry a display-name slug ("/users/12345/alex-rivera") and are
    often copied with extra trailing segments; only the id is needed.
    """

    site = _site_key(hostname(url))
    if site is None:
        return None
    segments = path_segments(url)
    if len(segments) < 2 or segments[0].casefold() != "users":
        return None
    return (site, segments[1]) if _USER_ID.match(segments[1]) else None
