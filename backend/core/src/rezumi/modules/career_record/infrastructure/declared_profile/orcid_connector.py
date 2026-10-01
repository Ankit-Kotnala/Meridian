"""ORCID public researcher-profile connector using the documented public API.

Not registered by default (see `registry.py::default_declared_profile_registry`
and `orcid_connector_enabled` in the API settings) — ORCID's Public API terms
restrict use to non-commercial purposes, and Rezumi is commercial. This
connector is built and tested so it's ready the moment that's cleared with
ORCID (a Member API agreement or written clearance), but it must stay off
until then.
"""

from __future__ import annotations

import asyncio
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

_ORCID_ID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", re.IGNORECASE)
_MAX_WORKS = 10
_TIMEOUT = 8.0


class OrcidDeclaredProfileConnector:
    """Reads a researcher's public ORCID works list (`orcid.org/<orcid-id>`)."""

    platform = "orcid"

    def supports(self, url: str) -> bool:
        return _orcid_id(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        orcid_id = _orcid_id(normalized)
        if orcid_id is None:
            raise DeclaredProfileFetchFailed("ORCID profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, orcid_id)

    def _fetch_sync(self, profile_url: str, orcid_id: str) -> DeclaredProfileFetchResult:
        payload = self._get_json(f"https://pub.orcid.org/v3.0/{orcid_id}/works")
        groups = payload.get("group") if isinstance(payload, dict) else None
        if not isinstance(groups, list):
            raise DeclaredProfileFetchFailed("ORCID profile did not expose public works")

        achievements: list[DeclaredProfileAchievement] = []
        for group in groups[:_MAX_WORKS]:
            if not isinstance(group, dict):
                continue
            summaries = group.get("work-summary")
            summary = summaries[0] if isinstance(summaries, list) and summaries else None
            if not isinstance(summary, dict):
                continue
            title_value = summary.get("title")
            title_block: dict[str, Any] = title_value if isinstance(title_value, dict) else {}
            nested_title = title_block.get("title")
            nested_title = nested_title if isinstance(nested_title, dict) else {}
            title = str(nested_title.get("value") or "").strip()
            if not title:
                continue
            journal_block = summary.get("journal-title")
            journal_block = journal_block if isinstance(journal_block, dict) else {}
            journal = str(journal_block.get("value") or "").strip()
            publication_date = summary.get("publication-date")
            publication_date = publication_date if isinstance(publication_date, dict) else {}
            year_block = publication_date.get("year")
            year_block = year_block if isinstance(year_block, dict) else {}
            year = year_block.get("value")
            parts = [f"Published in {journal}." if journal else "", str(year) if year else ""]
            statement = " ".join(part for part in parts if part) or "Public ORCID work record."
            work_url_block = summary.get("url")
            work_url_block = work_url_block if isinstance(work_url_block, dict) else {}
            work_url = work_url_block.get("value") or profile_url
            achievements.append(
                DeclaredProfileAchievement(
                    title=title[:300],
                    statement=statement,
                    source_url=str(work_url or profile_url),
                    excerpt=statement[:500],
                )
            )

        if not achievements:
            raise DeclaredProfileFetchFailed("ORCID profile did not expose public works")

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=tuple(achievements),
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed ORCID public API host
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(500_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("ORCID profile was not found") from exc
            raise DeclaredProfileFetchFailed("ORCID profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("ORCID profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))


def _orcid_id(url: str) -> str | None:
    """Return the ORCID iD a URL names, in canonical uppercase-checksum form."""

    if not host_matches(hostname(url), "orcid.org"):
        return None
    segments = path_segments(url)
    if not segments:
        return None
    candidate = segments[0].upper()
    return candidate if _ORCID_ID.match(candidate) else None
