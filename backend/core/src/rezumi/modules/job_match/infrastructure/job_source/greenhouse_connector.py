"""Greenhouse listing connector backed by deterministic fixtures (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from rezumi.modules.job_match.application.job_source_ports import JobSourceListing
from rezumi.modules.job_match.domain import JobMatchValidationError

from .fake_connector import _validate_listing

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[8]
    / "frontend"
    / "test-fixtures"
    / "job-source"
    / "greenhouse-listings.json"
)


class GreenhouseJobSourceConnector:
    platform = "greenhouse"

    async def fetch_listings(self, query: str) -> tuple[JobSourceListing, ...]:
        normalized = query.strip().casefold()
        payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        listings = payload.get("listings")
        if not isinstance(listings, list):
            raise JobMatchValidationError("fixture listings payload is invalid")
        validated = tuple(
            _validate_listing(item) for item in listings if isinstance(item, dict)
        )
        if not normalized:
            return validated
        return tuple(
            listing
            for listing in validated
            if normalized in listing.title.casefold()
            or normalized in (listing.company or "").casefold()
            or normalized in listing.source_text.casefold()
        )
