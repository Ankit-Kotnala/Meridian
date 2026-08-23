"""Remotive published job feed connector.

Remotive's stated usage terms (https://remotive.com/remote-jobs/api) cap free
callers at roughly 4 requests/day and require every listing shown elsewhere to
link back to its original Remotive URL. This connector is only ever invoked
from the scheduled catalog-sync pipeline (see
`apps.worker.rezumi_worker.config.WorkerSettings.job_catalog_sync_interval_seconds`,
defaulted to 6h = 4x/day) — never per-request — and `application_url` is
always preserved and must be surfaced as the attribution link wherever a
listing is displayed.
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

_URL = "https://remotive.com/api/remote-jobs"
_TIMEOUT = 10.0
_MAX_RESPONSE_BYTES = 5_000_000
_MAX_LISTINGS = 500
_USER_AGENT = "RezumiJobCatalog/1.0 (+https://rezumi.local; job-catalog sync)"


class RemotiveCatalogConnector:
    platform = "remotive"

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
        request = Request(  # noqa: S310 - fixed Remotive API host
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
    location = bounded_location(str(entry.get("candidate_required_location") or "")) or None
    description = plain_text(str(entry.get("description") or ""))
    category = str(entry.get("category") or "").strip()
    source_text = plain_text(" ".join(part for part in (category, description) if part))
    posted_at = _parse_date(entry.get("publication_date"))
    return CatalogJobListing(
        platform="remotive",
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
