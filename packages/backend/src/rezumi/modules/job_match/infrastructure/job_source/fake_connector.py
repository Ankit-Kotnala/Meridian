"""Deterministic job-source connector for local development and tests."""

from __future__ import annotations

import json
from pathlib import Path

from rezumi.modules.job_match.application.job_source_ports import JobSourceListing
from rezumi.modules.job_match.domain import JobMatchValidationError

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[7]
    / "test-fixtures"
    / "job-source"
    / "fake-listings.json"
)


def _validate_listing(payload: dict[str, object]) -> JobSourceListing:
    external_id = payload.get("externalId")
    title = payload.get("title")
    source_text = payload.get("sourceText")
    if not isinstance(external_id, str) or not external_id.strip():
        raise JobMatchValidationError("listing external id is invalid")
    if not isinstance(title, str) or not title.strip():
        raise JobMatchValidationError("listing title is invalid")
    if not isinstance(source_text, str) or len(source_text.strip()) < 20:
        raise JobMatchValidationError("listing source text is invalid")
    company = payload.get("company")
    location = payload.get("location")
    application_url = payload.get("applicationUrl")
    return JobSourceListing(
        external_id=external_id.strip(),
        title=title.strip(),
        company=company.strip() if isinstance(company, str) and company.strip() else None,
        location=location.strip() if isinstance(location, str) and location.strip() else None,
        application_url=(
            application_url.strip()
            if isinstance(application_url, str) and application_url.strip()
            else None
        ),
        source_text=source_text.strip(),
    )


class FakeJobSourceConnector:
    platform = "fake"

    async def fetch_listings(self, query: str) -> tuple[JobSourceListing, ...]:
        _ = query.strip()
        payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        listings = payload.get("listings")
        if not isinstance(listings, list):
            raise JobMatchValidationError("fixture listings payload is invalid")
        return tuple(_validate_listing(item) for item in listings if isinstance(item, dict))
