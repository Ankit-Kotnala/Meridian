"""Shared normalization for public profile connector payloads.

Provider APIs are public inputs, not trusted domain objects.  They vary in
shape, occasionally return strings where a number is expected, and may contain
control characters or unusable links.  Keep those quirks at the infrastructure
boundary so the application only receives bounded, reviewable values.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from rezumi.modules.career_record.application.declared_profile_ports import (
    normalize_declared_profile_url,
)
from rezumi.modules.career_record.domain.errors import CareerRecordValidationError

_MAX_PUBLIC_INTEGER = 10**12


def public_text(value: Any, *, limit: int = 2_000) -> str:
    """Return normalized, control-free, bounded public text."""

    if limit < 1:
        raise ValueError("public text limit must be positive")
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(
        character for character in text if not unicodedata.category(character).startswith("C")
    )
    return " ".join(text.split())[:limit].strip()


def positive_public_int(value: Any, *, maximum: int = _MAX_PUBLIC_INTEGER) -> int:
    """Parse a provider counter without raising or accepting absurd values."""

    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if 0 < value <= maximum else 0
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.isdigit() and len(candidate) <= len(str(maximum)):
            parsed = int(candidate)
            return parsed if 0 < parsed <= maximum else 0
    return 0


def safe_source_url(value: Any, fallback: str) -> str:
    """Keep only absolute HTTP(S) provenance URLs, otherwise use the profile."""

    candidate = public_text(value, limit=2_000)
    try:
        return normalize_declared_profile_url(candidate)
    except (CareerRecordValidationError, ValueError):
        return fallback
