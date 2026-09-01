"""Ashby public job-board API connector for India-located openings."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
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

_BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"
_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 5_000_000
_MAX_BOARDS = 250
_USER_AGENT = "RezumiJobCatalog/1.0 (+https://rezumi.local; job-catalog sync)"
_INDIA_LOCATION = re.compile(
    r"\b(?:india|bengaluru|bangalore|hyderabad|pune|mumbai|new delhi|delhi|"
    r"gurugram|gurgaon|noida|chennai|kolkata|ahmedabad|kochi)\b",
    re.IGNORECASE,
)
_BOARD_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")


@dataclass(frozen=True, slots=True)
class AshbyIndiaCatalogOptions:
    """Explicit public boards that may be read through Ashby's published API."""

    board_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.board_names:
            raise ValueError("at least one Ashby board name is required")
        if len(self.board_names) > _MAX_BOARDS:
            raise ValueError(f"at most {_MAX_BOARDS} Ashby board names are allowed")
        if len(set(self.board_names)) != len(self.board_names):
            raise ValueError("Ashby board names must be unique")
        if any(_BOARD_NAME.fullmatch(name) is None for name in self.board_names):
            raise ValueError("Ashby board names contain unsupported characters")


class AshbyIndiaCatalogConnector:
    """Enumerate India-located jobs from configured public Ashby boards."""

    platform = "ashby"

    def __init__(self, options: AshbyIndiaCatalogOptions) -> None:
        self._options = options

    async def iter_listings(self) -> AsyncIterator[CatalogJobListing]:
        for board_name in self._options.board_names:
            payload = await asyncio.to_thread(self._fetch, board_name)
            entries = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(entries, list):
                continue
            for entry in entries:
                listing = _listing(board_name, entry)
                if listing is not None:
                    yield listing

    def _fetch(self, board_name: str) -> Any:
        request = Request(  # noqa: S310 - fixed Ashby API host
            f"{_BASE_URL}/{quote(board_name)}",
            headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                body = response.read(_MAX_RESPONSE_BYTES)
        except (HTTPError, URLError, TimeoutError, OSError):
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}


def _listing(board_name: str, entry: Any) -> CatalogJobListing | None:
    if not isinstance(entry, dict):
        return None
    job_id = str(entry.get("id") or "").strip()
    raw_title = str(entry.get("title") or "").strip()
    application_url = str(entry.get("applyUrl") or entry.get("jobUrl") or "").strip()
    raw_location = str(entry.get("location") or "").strip()
    secondary_locations = entry.get("secondaryLocations")
    if isinstance(secondary_locations, list):
        raw_location = "; ".join(
            location
            for location in [raw_location, *(str(value).strip() for value in secondary_locations)]
            if location
        )
    if (
        not job_id
        or not raw_title
        or not _INDIA_LOCATION.search(raw_location)
        or not application_url.startswith(("http://", "https://"))
        or len(application_url) > 2_048
    ):
        return None
    return CatalogJobListing(
        platform="ashby",
        external_id=f"{board_name}:{job_id}",
        title=bounded_title(raw_title),
        company=bounded_company(board_name) or None,
        location=bounded_location(raw_location) or None,
        remote=bool(entry.get("isRemote")) or "remote" in raw_location.casefold(),
        application_url=application_url,
        source_text=plain_text(str(entry.get("descriptionPlain") or ""))
        or bounded_title(raw_title),
        posted_at=_parse_date(entry.get("publishedAt")),
    )


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
