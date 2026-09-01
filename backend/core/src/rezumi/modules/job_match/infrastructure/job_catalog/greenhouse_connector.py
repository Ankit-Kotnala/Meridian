"""Greenhouse public Job Board API connector for configured employer boards."""

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

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 5_000_000
_MAX_BOARDS = 250
_USER_AGENT = "RezumiJobCatalog/1.0 (+https://rezumi.local; job-catalog sync)"
_INDIA_LOCATION = re.compile(
    r"\b(?:india|bengaluru|bangalore|hyderabad|pune|mumbai|new delhi|delhi|"
    r"gurugram|gurgaon|noida|chennai|kolkata|ahmedabad|kochi)\b",
    re.IGNORECASE,
)
_BOARD_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")


@dataclass(frozen=True, slots=True)
class GreenhouseIndiaCatalogOptions:
    """Explicit public boards that may be read through Greenhouse's API."""

    board_tokens: tuple[str, ...]
    include_global: bool = False
    include_content: bool = True

    def __post_init__(self) -> None:
        if not self.board_tokens:
            raise ValueError("at least one Greenhouse board token is required")
        if len(self.board_tokens) > _MAX_BOARDS:
            raise ValueError(f"at most {_MAX_BOARDS} Greenhouse board tokens are allowed")
        if len(set(self.board_tokens)) != len(self.board_tokens):
            raise ValueError("Greenhouse board tokens must be unique")
        if any(_BOARD_TOKEN.fullmatch(token) is None for token in self.board_tokens):
            raise ValueError("Greenhouse board tokens contain unsupported characters")


class GreenhouseIndiaCatalogConnector:
    """Enumerate configured public Greenhouse boards with optional India filtering."""

    platform = "greenhouse"

    def __init__(self, options: GreenhouseIndiaCatalogOptions) -> None:
        self._options = options

    async def iter_listings(self) -> AsyncIterator[CatalogJobListing]:
        for board_token in self._options.board_tokens:
            payload = await asyncio.to_thread(
                self._fetch,
                board_token,
                include_content=self._options.include_content,
            )
            entries = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(entries, list):
                continue
            for entry in entries:
                listing = _listing(
                    board_token,
                    entry,
                    include_global=self._options.include_global,
                )
                if listing is not None:
                    yield listing

    def _fetch(self, board_token: str, *, include_content: bool) -> Any:
        content_query = "?content=true" if include_content else ""
        request = Request(  # noqa: S310 - fixed Greenhouse API host
            f"{_BASE_URL}/{quote(board_token)}/jobs{content_query}",
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


def _listing(
    board_token: str,
    entry: Any,
    *,
    include_global: bool = False,
) -> CatalogJobListing | None:
    if not isinstance(entry, dict):
        return None
    job_id = str(entry.get("id") or "").strip()
    raw_title = str(entry.get("title") or "").strip()
    application_url = str(entry.get("absolute_url") or "").strip()
    location_data = entry.get("location")
    raw_location = str(location_data.get("name") or "") if isinstance(location_data, dict) else ""
    if (
        not job_id
        or not raw_title
        or (not include_global and not _INDIA_LOCATION.search(raw_location))
        or not application_url.startswith(("http://", "https://"))
        or len(application_url) > 2_048
    ):
        return None
    return CatalogJobListing(
        platform="greenhouse",
        external_id=f"{board_token}:{job_id}",
        title=bounded_title(raw_title),
        company=bounded_company(board_token) or None,
        location=bounded_location(raw_location) or None,
        remote="remote" in raw_location.casefold(),
        application_url=application_url,
        source_text=plain_text(str(entry.get("content") or "")) or bounded_title(raw_title),
        posted_at=_parse_date(entry.get("updated_at")),
    )


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
