"""Ports for declared-link profile enrichment (Phase 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import unquote, urlsplit, urlunsplit

from rezumi.modules.career_record.domain.errors import (
    CareerRecordConflict,
    CareerRecordValidationError,
)

# Punctuation a resume line commonly wraps around a link -- "(github.com/alex)."
# or "<https://alex.dev>" -- which must not survive into the URL a connector
# matches on, or a perfectly good profile link resolves to "unsupported".
_TRAILING_PUNCTUATION = ".,;:!?*\u2018\u2019\u201c\u201d\"'"
_CLOSING_BRACKETS = {")": "(", "]": "[", "}": "{", ">": "<"}
_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True, slots=True)
class DeclaredProfileAchievement:
    """One public achievement extracted from a user-declared profile URL."""

    title: str
    statement: str
    source_url: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class DeclaredProfileFetchResult:
    platform: str
    profile_url: str
    fetched_at: datetime
    achievements: tuple[DeclaredProfileAchievement, ...]


class DeclaredProfileConnector(Protocol):
    """Fetch public achievements from a single declared profile URL."""

    platform: str

    def supports(self, url: str) -> bool:
        """Return true when this connector owns the declared URL host/path."""

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        """Fetch achievements from the declared public profile."""


class DeclaredProfileUnsupported(CareerRecordValidationError):
    """Raised when no connector may fetch the declared URL."""


class DeclaredProfileFetchFailed(CareerRecordConflict):
    """Raised when a permitted fetch fails safely."""


def strip_url_wrapping(value: str) -> str:
    """Drop quotes/brackets/sentence punctuation a resume wrapped around a link.

    A closing bracket is only dropped when the URL does not open one itself, so
    a genuine Wikipedia-style path such as ``/wiki/Foo_(bar)`` survives intact.
    """

    trimmed = value.strip()
    while trimmed and trimmed[0] in "(<[{\"'\u2018\u201c":
        trimmed = trimmed[1:]
    while trimmed:
        last = trimmed[-1]
        opener = _CLOSING_BRACKETS.get(last)
        if opener is not None:
            if trimmed.count(opener) >= trimmed.count(last):
                break
            trimmed = trimmed[:-1]
            continue
        if last in _TRAILING_PUNCTUATION:
            trimmed = trimmed[:-1]
            continue
        break
    return trimmed.strip()


def canonical_http_url(value: str) -> str:
    """Return an absolute HTTP(S) URL in a stable, comparable form.

    Host casing, a redundant default port, a trailing FQDN dot, and duplicate
    path slashes are all normalized away so ``https://GitHub.com:443//Alex/``
    and ``https://github.com/Alex`` route to the same connector and dedupe as
    the same declared link.
    """

    trimmed = strip_url_wrapping(value)
    parsed = urlsplit(trimmed)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise CareerRecordValidationError("profile link must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise CareerRecordValidationError("profile link must not contain credentials")
    scheme = parsed.scheme.casefold()
    host = parsed.hostname.casefold().rstrip(".")
    if not host:
        raise CareerRecordValidationError("profile link must include a hostname")
    netloc = host
    if parsed.port is not None and parsed.port != _DEFAULT_PORTS[scheme]:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path
    while "//" in path:
        path = path.replace("//", "/")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parsed.query, parsed.fragment))


def normalize_declared_profile_url(url: str) -> str:
    """Validate and canonicalize a user-declared profile URL before routing."""

    return canonical_http_url(url)


def hostname(url: str) -> str:
    """Return the lowercase registrable host of ``url`` without a ``www.`` prefix."""

    host = (urlsplit(url).hostname or "").casefold().rstrip(".")
    return host.removeprefix("www.")


def host_matches(host: str, base: str) -> bool:
    """Whether ``host`` is ``base`` or any subdomain of it.

    Host routing has to be suffix-aware: ``de.linkedin.com`` and
    ``gist.github.com`` are the same platform as their apex domain, and an
    exact-match-only check silently sends them to the generic HTML fallback.
    """

    normalized = host.casefold().rstrip(".").removeprefix("www.")
    return normalized == base or normalized.endswith(f".{base}")


def path_segments(url: str) -> tuple[str, ...]:
    """Return the non-empty, URL-decoded path segments of ``url``."""

    return tuple(unquote(part) for part in urlsplit(url).path.split("/") if part)
