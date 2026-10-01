"""OpenAlex researcher-profile connector using the documented public API.

This is the cross-domain research connector: OpenAlex indexes scholarly output
across every field, so one connector serves a clinician citing PubMed-indexed
papers, an economist citing journal articles, a legal academic, and a
management researcher alike.

It is registered by default where the ORCID connector is not. ORCID's own
Public API restricts use to non-commercial purposes and Rezumi is commercial
(see `orcid_connector.py`); OpenAlex publishes the same publication record
under CC0 with no key and no such restriction, and resolves an ORCID iD
directly. A user pasting an `orcid.org` link therefore gets their works read
from OpenAlex rather than a refusal - and if ORCID is ever cleared, its
connector is registered ahead of this one and wins the route.

Verified against live data on 2026-08-30.
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
from rezumi.modules.career_record.infrastructure.declared_profile.normalization import (
    positive_public_int,
)

_ORCID_ID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_OPENALEX_AUTHOR = re.compile(r"^A\d{1,20}$")
_MAX_WORKS = 5
_TIMEOUT = 8.0
_ATTRIBUTION = "Source: OpenAlex (CC0)."


class OpenAlexDeclaredProfileConnector:
    """Reads a researcher's public publication record from OpenAlex."""

    platform = "openalex"

    def supports(self, url: str) -> bool:
        return _author_key(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        key = _author_key(normalized)
        if key is None:
            raise DeclaredProfileFetchFailed("Research profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, key)

    def _fetch_sync(self, profile_url: str, author_key: str) -> DeclaredProfileFetchResult:
        author = self._get_json(f"https://api.openalex.org/authors/{author_key}")
        if not isinstance(author, dict) or not author.get("id"):
            raise DeclaredProfileFetchFailed("Research profile was not found")

        name = str(author.get("display_name") or "Researcher").strip()
        works_count = positive_public_int(author.get("works_count"))
        cited_by = positive_public_int(author.get("cited_by_count"))
        stats = author.get("summary_stats") if isinstance(author.get("summary_stats"), dict) else {}
        h_index = positive_public_int((stats or {}).get("h_index"))
        institution = _institution(author)

        parts = [f"{works_count} indexed works, {cited_by} citations"]
        if h_index > 0:
            parts.append(f"h-index {h_index}")
        summary = ", ".join(parts) + "."
        if institution:
            summary = f"{summary} Last known affiliation: {institution}."
        summary = f"{summary} {_ATTRIBUTION}"

        if works_count == 0:
            raise DeclaredProfileFetchFailed(
                "Research profile did not expose any indexed publications"
            )

        achievements = [
            DeclaredProfileAchievement(
                title=f"{name} on OpenAlex",
                statement=summary,
                source_url=profile_url,
                excerpt=summary[:500],
            )
        ]
        achievements.extend(self._top_works(str(author["id"]).rsplit("/", 1)[-1], profile_url))
        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=tuple(achievements),
        )

    def _top_works(self, author_id: str, profile_url: str) -> list[DeclaredProfileAchievement]:
        payload = self._get_json(
            f"https://api.openalex.org/works?filter=author.id:{author_id}"
            f"&sort=cited_by_count:desc&per-page={_MAX_WORKS}"
        )
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            return []
        works: list[DeclaredProfileAchievement] = []
        for work in results[:_MAX_WORKS]:
            if not isinstance(work, dict):
                continue
            title = str(work.get("title") or "").strip()
            if not title:
                continue
            parts: list[str] = []
            venue = _venue(work)
            year = work.get("publication_year")
            if venue and isinstance(year, int):
                parts.append(f"Published in {venue}, {year}.")
            elif venue:
                parts.append(f"Published in {venue}.")
            elif isinstance(year, int):
                parts.append(f"Published {year}.")
            citations = positive_public_int(work.get("cited_by_count"))
            if citations > 0:
                parts.append(f"{citations} citations.")
            statement = " ".join([*parts, _ATTRIBUTION])
            works.append(
                DeclaredProfileAchievement(
                    title=title[:200],
                    statement=statement,
                    source_url=str(work.get("doi") or work.get("id") or profile_url),
                    excerpt=statement[:500],
                )
            )
        return works

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed OpenAlex API host
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
                raise DeclaredProfileFetchFailed("Research profile was not found") from exc
            if exc.code == 429:
                raise DeclaredProfileFetchFailed(
                    "OpenAlex is throttling public reads right now. Try again later."
                ) from exc
            raise DeclaredProfileFetchFailed("Research profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("Research profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))


def _institution(author: dict[str, Any]) -> str:
    institutions = author.get("last_known_institutions")
    if isinstance(institutions, list) and institutions and isinstance(institutions[0], dict):
        return str(institutions[0].get("display_name") or "").strip()
    return ""


def _venue(work: dict[str, Any]) -> str:
    location = work.get("primary_location")
    if not isinstance(location, dict):
        return ""
    source = location.get("source")
    if not isinstance(source, dict):
        return ""
    return str(source.get("display_name") or "").strip()


def _author_key(url: str) -> str | None:
    """Return the OpenAlex author lookup key an ORCID or OpenAlex URL names.

    OpenAlex resolves an author by full ORCID URL, so an `orcid.org` link needs
    no extra lookup step.
    """

    host = hostname(url)
    segments = path_segments(url)
    if not segments:
        return None
    if host_matches(host, "orcid.org"):
        orcid = segments[0].upper()
        return f"https://orcid.org/{orcid}" if _ORCID_ID.match(orcid) else None
    if host_matches(host, "openalex.org"):
        candidate = segments[-1].upper() if segments[0].casefold() == "authors" else segments[0]
        candidate = candidate.upper()
        return candidate if _OPENALEX_AUTHOR.match(candidate) else None
    return None
