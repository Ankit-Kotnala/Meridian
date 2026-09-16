"""Deterministic catalog browse filters shared by query tests and adapters."""

from __future__ import annotations

import re

from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing

_MAX_TERMS = 8
_MAX_TERM_LENGTH = 40
_MAX_LOCATION_LENGTH = 120

_SENIORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("internship", re.compile(r"\b(intern|internship|trainee|apprentice)\b", re.I)),
    ("principal", re.compile(r"\b(principal|distinguished|fellow|director|head of|vp)\b", re.I)),
    ("staff", re.compile(r"\b(staff|architect)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr\.?|lead)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr\.?|graduate|entry[- ]level|associate)\b", re.I)),
)

_REMOTE_PATTERN = re.compile(r"\b(remote|anywhere|worldwide|work from home)\b", re.I)
_HYBRID_PATTERN = re.compile(r"\bhybrid\b", re.I)


def normalized_terms(keywords: tuple[str, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for raw in keywords:
        term = raw.strip()[:_MAX_TERM_LENGTH]
        if not term:
            continue
        terms.append(term)
        if len(terms) >= _MAX_TERMS:
            break
    return tuple(terms)


def term_regex(term: str) -> str:
    escaped = re.escape(term.strip()[:_MAX_TERM_LENGTH])
    if len(term.strip()) <= 3:
        return rf"\b{escaped}\b"
    return escaped


def listing_seniority(title: str) -> str:
    for value, pattern in _SENIORITY_PATTERNS:
        if pattern.search(title):
            return value
    return "mid"


def listing_work_model(listing: CatalogJobListing) -> str:
    text = f"{listing.title} {listing.location or ''}"
    if _HYBRID_PATTERN.search(text):
        return "hybrid"
    if listing.remote is True or _REMOTE_PATTERN.search(text):
        return "remote"
    return "onsite"


def listing_matches_browse(
    listing: CatalogJobListing,
    *,
    keywords: tuple[str, ...],
    platform: str | None = None,
    location: str | None = None,
    seniority: str | None = None,
    work_model: str | None = None,
) -> bool:
    if platform and listing.platform != platform:
        return False
    needle = (location or "").strip()[:_MAX_LOCATION_LENGTH]
    if needle and needle.casefold() not in (listing.location or "").casefold():
        return False
    if seniority and listing_seniority(listing.title) != seniority:
        return False
    if work_model and listing_work_model(listing) != work_model:
        return False
    haystack = f"{listing.title} {listing.company or ''}"
    for term in normalized_terms(keywords):
        if re.search(term_regex(term), haystack, flags=re.I) is None:
            return False
    return True
