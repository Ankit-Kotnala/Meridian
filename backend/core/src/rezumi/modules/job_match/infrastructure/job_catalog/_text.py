"""Shared plain-text normalization for hostile third-party job descriptions."""

from __future__ import annotations

import re
from html import unescape

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
# Job Match's own domain validation rejects any ord < 32 character other than
# \n, \r, \t. Third-party HTML can carry stray control bytes that survive
# whitespace collapsing (e.g. \x00, \x0b); strip them here so every field this
# module hands to JobMatchService is already guaranteed to pass that check.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_SOURCE_TEXT = 3_000
_MAX_TITLE = 300
_MAX_COMPANY = 300
_MAX_LOCATION = 240


def plain_text(html_or_text: str, *, max_length: int = _MAX_SOURCE_TEXT) -> str:
    """Strip HTML tags and collapse whitespace; never executes/parses as markup."""
    without_tags = _TAG.sub(" ", html_or_text)
    without_control = _CONTROL_CHARACTERS.sub("", unescape(without_tags))
    normalized = _WHITESPACE.sub(" ", without_control).strip()
    return normalized[:max_length]


def bounded(value: str, *, max_length: int) -> str:
    """Collapse whitespace and hard-cap length for a plain (non-HTML) field."""
    without_control = _CONTROL_CHARACTERS.sub("", value)
    return _WHITESPACE.sub(" ", without_control).strip()[:max_length]


def bounded_title(value: str) -> str:
    return bounded(value, max_length=_MAX_TITLE)


def bounded_company(value: str) -> str:
    return bounded(value, max_length=_MAX_COMPANY)


def bounded_location(value: str) -> str:
    return bounded(value, max_length=_MAX_LOCATION)
