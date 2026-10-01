"""Small, non-fetching helpers for recovering document web hyperlinks."""

from __future__ import annotations

from urllib.parse import urlsplit

_HTTP_SCHEMES = frozenset({"http", "https"})
_MAX_HYPERLINK_LENGTH = 2_048


def safe_http_hyperlink(value: object) -> str | None:
    """Return an external HTTP(S) link that is safe to retain as document data.

    This helper deliberately does not resolve DNS, follow redirects, or make a
    network request. It only admits the kind of target that can represent a
    public web link; enrichment applies its own SSRF and platform policy later.
    """

    if not isinstance(value, str):
        return None
    target = value.strip()
    if not target or len(target) > _MAX_HYPERLINK_LENGTH:
        return None
    if any(character.isspace() or ord(character) < 0x20 for character in target):
        return None
    try:
        parsed = urlsplit(target)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() not in _HTTP_SCHEMES
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or (port is not None and not 1 <= port <= 65_535)
    ):
        return None
    return target


def append_hyperlink_targets(value: str, targets: tuple[str, ...]) -> tuple[str, bool]:
    """Make recovered targets visible to the existing source-anchored parser."""

    result = value
    appended = False
    seen: set[str] = set()
    for target in targets:
        normalized = safe_http_hyperlink(target)
        if normalized is None or normalized.casefold() in seen:
            continue
        seen.add(normalized.casefold())
        if normalized.casefold() in result.casefold():
            continue
        result = f"{result} {normalized}".strip()
        appended = True
    return result, appended
