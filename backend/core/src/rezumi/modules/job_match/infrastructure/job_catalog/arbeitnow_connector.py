"""Arbeitnow published job-board API connector.

Arbeitnow's terms require a link back to arbeitnow.com wherever data from
their API is shown; `application_url` (their own listing URL) is always
preserved for that purpose.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
from rezumi.modules.job_match.infrastructure.job_catalog._text import (
    bounded_company,
    bounded_location,
    bounded_title,
    plain_text,
)

_BASE_URL = "https://www.arbeitnow.com/api/job-board-api"
_TIMEOUT = 10.0
_MAX_RESPONSE_BYTES = 5_000_000
_MAX_PAGES = 30
_MAX_LISTINGS = 3_000
_USER_AGENT = "RezumiJobCatalog/1.0 (+https://rezumi.local; job-catalog sync)"


class ArbeitnowCatalogConnector:
    platform = "arbeitnow"

    async def iter_listings(self) -> AsyncIterator[CatalogJobListing]:
        emitted = 0
        page = 1
        while page <= _MAX_PAGES and emitted < _MAX_LISTINGS:
            payload = await asyncio.to_thread(self._fetch, page)
            entries = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(entries, list) or not entries:
                return
            for entry in entries:
                if emitted >= _MAX_LISTINGS:
                    return
                listing = _listing(entry)
                if listing is not None:
                    emitted += 1
                    yield listing
            links = payload.get("links") if isinstance(payload, dict) else None
            if not isinstance(links, dict) or not links.get("next"):
                return
            page += 1

    def _fetch(self, page: int) -> Any:
        request = Request(  # noqa: S310 - fixed Arbeitnow API host
            f"{_BASE_URL}?page={page}",
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
    external_id = str(entry.get("slug") or "").strip()
    raw_title = str(entry.get("title") or "").strip()
    application_url = str(entry.get("url") or "").strip()
    if (
        not external_id
        or not raw_title
        or not application_url.startswith(("http://", "https://"))
        or len(application_url) > 2_048
    ):
        return None
    title = bounded_title(raw_title)
    company = bounded_company(str(entry.get("company_name") or "")) or None
    location = bounded_location(str(entry.get("location") or "")) or None
    description = plain_text(str(entry.get("description") or ""))
    tags = entry.get("tags")
    job_types = entry.get("job_types")
    tag_text = " ".join(str(tag) for tag in tags) if isinstance(tags, list) else ""
    type_text = " ".join(str(kind) for kind in job_types) if isinstance(job_types, list) else ""
    source_text = plain_text(" ".join(part for part in (tag_text, type_text, description) if part))
    posted_at = _parse_timestamp(entry.get("created_at"))
    return CatalogJobListing(
        platform="arbeitnow",
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        remote=bool(entry.get("remote")) if "remote" in entry else None,
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
