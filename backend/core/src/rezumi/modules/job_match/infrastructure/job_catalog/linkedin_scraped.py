"""Map scraped LinkedIn job exports into shared catalog listings."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
from rezumi.modules.job_match.infrastructure.job_catalog._text import (
    bounded_company,
    bounded_location,
    bounded_title,
    plain_text,
)

PLATFORM = "linkedin"
_MAX_APPLICATION_URL = 2_048


def load_scraped_jobs(path: Path) -> tuple[dict[str, Any], ...]:
    """Load job records from a scraped-jobs JSON export.

    Exports wrap the array in a single SQL-query key; this accepts either that
    shape or a bare array of records.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        values = list(payload.values())
        if len(values) != 1 or not isinstance(values[0], list):
            raise ValueError("Unexpected scraped-jobs JSON shape.")
        records = values[0]
    else:
        raise ValueError("Unexpected scraped-jobs JSON shape.")
    return tuple(record for record in records if isinstance(record, dict))


def listing_from_scraped_record(record: dict[str, Any]) -> CatalogJobListing | None:
    external_id = str(record.get("job_id") or "").strip()
    raw_title = str(record.get("job_title") or "").strip()
    application_url = str(record.get("job_url") or "").strip()
    if (
        not external_id
        or not raw_title
        or not application_url.startswith(("http://", "https://"))
        or len(application_url) > _MAX_APPLICATION_URL
    ):
        return None

    title = bounded_title(raw_title)
    company = bounded_company(str(record.get("company_name") or "")) or None
    location = bounded_location(str(record.get("job_location") or "")) or None
    source_text = _source_text(record)
    posted_at = _parse_datetime(record.get("posted_at"))
    return CatalogJobListing(
        platform=PLATFORM,
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        remote=_infer_remote(location),
        application_url=application_url,
        source_text=source_text or title,
        posted_at=posted_at,
    )


def _source_text(record: dict[str, Any]) -> str:
    parts = (
        record.get("seniority_level"),
        record.get("employment_type"),
        record.get("industries"),
        record.get("job_function"),
        record.get("job_description"),
    )
    combined = " ".join(str(part).strip() for part in parts if part)
    return plain_text(combined)


def _infer_remote(location: str | None) -> bool | None:
    if not location:
        return None
    lowered = location.casefold()
    if any(token in lowered for token in ("remote", "anywhere", "work from home")):
        return True
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
