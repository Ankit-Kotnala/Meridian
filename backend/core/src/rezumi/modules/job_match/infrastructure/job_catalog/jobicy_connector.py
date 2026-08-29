"""Jobicy published remote-jobs API connector.

Jobicy's API response embeds its own usage notice on every call ("Please
ensure Jobicy is clearly credited with a direct link to the source, and all
application buttons redirect to the original job URL") — `application_url`
is always preserved for that purpose. The feed caps a single call at 100
listings and offers no offset/cursor parameter, so one connector run returns
its most recent ~100 open listings.
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

_URL = "https://jobicy.com/api/v2/remote-jobs?count=100"
_TIMEOUT = 10.0
_MAX_RESPONSE_BYTES = 5_000_000
_MAX_LISTINGS = 100
_USER_AGENT = "RezumiJobCatalog/1.0 (+https://rezumi.local; job-catalog sync)"


class JobicyCatalogConnector:
    platform = "jobicy"

    async def iter_listings(self) -> AsyncIterator[CatalogJobListing]:
        payload = await asyncio.to_thread(self._fetch)
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            return
        for entry in jobs[:_MAX_LISTINGS]:
            listing = _listing(entry)
            if listing is not None:
                yield listing

    def _fetch(self) -> Any:
        request = Request(  # noqa: S310 - fixed Jobicy API host
            _URL,
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
    external_id = str(entry.get("id") or "").strip()
    raw_title = str(entry.get("jobTitle") or "").strip()
    application_url = str(entry.get("url") or "").strip()
    if (
        not external_id
        or not raw_title
        or not application_url.startswith(("http://", "https://"))
        or len(application_url) > 2_048
    ):
        return None
    title = bounded_title(raw_title)
    company = bounded_company(str(entry.get("companyName") or "")) or None
    location = bounded_location(str(entry.get("jobGeo") or "")) or None
    industries = entry.get("jobIndustry")
    types = entry.get("jobType")
    industry_text = (
        " ".join(str(item) for item in industries) if isinstance(industries, list) else ""
    )
    type_text = " ".join(str(item) for item in types) if isinstance(types, list) else ""
    description = plain_text(str(entry.get("jobDescription") or entry.get("jobExcerpt") or ""))
    source_text = plain_text(
        " ".join(part for part in (industry_text, type_text, description) if part)
    )
    posted_at = _parse_date(entry.get("pubDate"))
    return CatalogJobListing(
        platform="jobicy",
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        remote=True,
        application_url=application_url,
        source_text=source_text or title,
        posted_at=posted_at,
    )


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
