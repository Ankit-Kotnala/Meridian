"""Himalayas published remote-jobs API connector.

Himalayas is a dedicated remote-work job board; every listing embeds an
"Originally posted on Himalayas" attribution notice, and `application_url`
(the Himalayas listing page, which itself redirects to the employer) is
always preserved. The feed supports cursor-based pagination (their own
documented, preferred alternative to the deprecated offset parameter — see
the `comments` field returned on every call), which is what makes this
connector able to pull a genuinely large, varied slice of open listings
rather than a single fixed-size page.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
from rezumi.modules.job_match.infrastructure.job_catalog._text import (
    bounded_company,
    bounded_location,
    bounded_title,
    plain_text,
)

_BASE_URL = "https://himalayas.app/jobs/api"
_PAGE_LIMIT = 100
_TIMEOUT = 10.0
_MAX_RESPONSE_BYTES = 5_000_000
_MAX_PAGES = 30
_MAX_LISTINGS = 3_000
_USER_AGENT = "RezumiJobCatalog/1.0 (+https://rezumi.local; job-catalog sync)"


class HimalayasCatalogConnector:
    platform = "himalayas"

    async def iter_listings(self) -> AsyncIterator[CatalogJobListing]:
        emitted = 0
        page = 0
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while page < _MAX_PAGES and emitted < _MAX_LISTINGS:
            payload = await asyncio.to_thread(self._fetch, cursor)
            entries = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(entries, list) or not entries:
                return
            for entry in entries:
                if emitted >= _MAX_LISTINGS:
                    return
                listing = _listing(entry)
                if listing is not None:
                    emitted += 1
                    yield listing
            next_cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
                return
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            page += 1

    def _fetch(self, cursor: str | None) -> Any:
        url = f"{_BASE_URL}?limit={_PAGE_LIMIT}"
        if cursor:
            url = f"{url}&cursor={quote(cursor)}"
        request = Request(  # noqa: S310 - fixed Himalayas API host
            url,
            headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                body = response.read(_MAX_RESPONSE_BYTES)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}


def _listing(entry: Any) -> CatalogJobListing | None:
    if not isinstance(entry, dict):
        return None
    external_id = str(entry.get("guid") or "").strip()
    raw_title = str(entry.get("title") or "").strip()
    application_url = str(entry.get("applicationLink") or entry.get("guid") or "").strip()
    if (
        not external_id
        or not raw_title
        or not application_url.startswith(("http://", "https://"))
        or len(application_url) > 2_048
    ):
        return None
    title = bounded_title(raw_title)
    company = bounded_company(str(entry.get("companyName") or "")) or None
    locations = entry.get("locationRestrictions")
    location = (
        bounded_location(", ".join(str(item) for item in locations))
        if isinstance(locations, list) and locations
        else None
    )
    categories = entry.get("categories")
    category_text = (
        " ".join(str(item) for item in categories) if isinstance(categories, list) else ""
    )
    description = plain_text(str(entry.get("description") or entry.get("excerpt") or ""))
    source_text = plain_text(" ".join(part for part in (category_text, description) if part))
    posted_at = _parse_timestamp(entry.get("pubDate"))
    return CatalogJobListing(
        platform="himalayas",
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        remote=True,
        application_url=application_url,
        source_text=source_text or title,
        posted_at=posted_at,
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
