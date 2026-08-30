"""SSRF-aware bounded HTTP(S) fetch for declared public profile pages."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileFetchFailed,
)

# Structural chrome present on nearly every personal site, carrying no
# achievement content. Reading it as profile text is what turns a portfolio
# import into a list of menu items ("Home", "About", "Contact").
_CHROME_TAGS = frozenset({"nav", "header", "footer", "aside", "form", "dialog"})
_NON_TEXT_TAGS = frozenset(
    {"script", "style", "noscript", "template", "svg", "select", "button", "iframe"}
)
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4"})
_BLOCK_TAGS = frozenset(
    {"br", "p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
)
_MAX_HEADINGS = 40


class _HeaderMapping(Protocol):
    def get(self, name: str, default: str | None = None) -> str: ...


class _ReadableResponse(Protocol):
    headers: _HeaderMapping

    def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class SafeHttpOptions:
    max_bytes: int = 250_000
    timeout_seconds: float = 6.0
    max_redirects: int = 5

    def __post_init__(self) -> None:
        if self.max_bytes < 20 or self.timeout_seconds <= 0 or self.max_redirects < 0:
            raise ValueError("safe HTTP limits are invalid")


@dataclass(frozen=True, slots=True)
class SafeHttpPage:
    final_url: str
    title: str | None
    text: str
    description: str | None = None
    headings: tuple[str, ...] = field(default_factory=tuple)


class SafeHttpFetcher:
    """Fetch bounded public HTML/text with the same SSRF controls as job URL import."""

    def __init__(self, options: SafeHttpOptions | None = None) -> None:
        self._options = options or SafeHttpOptions()
        self._opener = build_opener(_NoRedirect)

    async def fetch(self, url: str) -> SafeHttpPage:
        return await asyncio.to_thread(self._fetch_sync, url)

    def _fetch_sync(self, url: str) -> SafeHttpPage:
        current = _validate_url(url)
        for _ in range(self._options.max_redirects + 1):
            request = Request(  # noqa: S310 - current is validated before every request.
                current,
                headers={
                    "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
                    "User-Agent": "RezumiDeclaredProfile/1.0",
                },
                method="GET",
            )
            try:
                with self._opener.open(request, timeout=self._options.timeout_seconds) as response:
                    return self._read_response(current, response)
            except HTTPError as exc:
                if 300 <= exc.code < 400:
                    location = exc.headers.get("Location")
                    if not location:
                        raise DeclaredProfileFetchFailed("redirect missing location") from exc
                    current = _validate_url(urljoin(current, location))
                    continue
                raise DeclaredProfileFetchFailed("public profile page could not be read") from exc
            except (TimeoutError, URLError, OSError) as exc:
                raise DeclaredProfileFetchFailed("public profile page could not be read") from exc
        raise DeclaredProfileFetchFailed("too many redirects while reading public profile page")

    def _read_response(self, final_url: str, response: _ReadableResponse) -> SafeHttpPage:
        headers = response.headers
        content_type = headers.get("Content-Type", "text/plain")
        if not _allowed_content_type(content_type):
            raise DeclaredProfileFetchFailed("unsupported profile page content type")
        payload = response.read(self._options.max_bytes + 1)
        if len(payload) > self._options.max_bytes:
            raise DeclaredProfileFetchFailed("public profile page is too large")
        charset = _charset(content_type)
        decoded = payload.decode(charset, errors="replace")
        description: str | None = None
        headings: tuple[str, ...] = ()
        if _is_html(content_type):
            parser = _TextExtractor()
            parser.feed(decoded)
            parser.close()
            text = parser.text()
            title = parser.title()
            description = parser.description()
            headings = parser.headings()
        else:
            text = decoded
            title = None
        normalized = _plain_text(text)
        if len(normalized) < 20 and not description:
            raise DeclaredProfileFetchFailed("public profile page did not contain usable text")
        return SafeHttpPage(
            final_url=final_url,
            title=title,
            text=normalized,
            description=description,
            headings=headings,
        )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class _TextExtractor(HTMLParser):
    """Pull readable body text, the page summary, and its headings.

    A meta description (or og:description) is usually the most accurate
    one-line summary a personal site publishes about itself, and headings mark
    where its real content starts. Both used to be discarded along with the
    rest of the tag attributes, leaving an undifferentiated blob of every
    string on the page - navigation chrome and cookie banner included.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chrome_depth = 0
        self._title_depth = 0
        self._heading_depth = 0
        self._chunks: list[str] = []
        self._title: list[str] = []
        self._heading: list[str] = []
        self._headings: list[str] = []
        self._description: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered == "meta":
            self._read_meta(attrs)
            return
        if lowered in _NON_TEXT_TAGS:
            self._skip_depth += 1
        if lowered in _CHROME_TAGS:
            self._chrome_depth += 1
        if lowered == "title":
            self._title_depth += 1
        if lowered in _HEADING_TAGS and not self._chrome_depth:
            self._heading_depth += 1
            self._heading = []
        if lowered in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "meta":
            self._read_meta(attrs)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in _NON_TEXT_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if lowered in _CHROME_TAGS and self._chrome_depth:
            self._chrome_depth -= 1
        if lowered == "title" and self._title_depth:
            self._title_depth -= 1
        if lowered in _HEADING_TAGS and self._heading_depth:
            self._heading_depth -= 1
            heading = _plain_text(" ".join(self._heading))
            if heading and len(self._headings) < _MAX_HEADINGS:
                self._headings.append(heading[:200])
            self._heading = []
        if lowered in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._title_depth:
            self._title.append(data)
            return
        if self._heading_depth:
            self._heading.append(data)
        if self._chrome_depth:
            return
        self._chunks.append(data)

    def _read_meta(self, attrs: list[tuple[str, str | None]]) -> None:
        if self._description is not None:
            return
        mapping = {name.casefold(): (value or "") for name, value in attrs}
        key = (mapping.get("name") or mapping.get("property") or "").casefold()
        if key not in {"description", "og:description", "twitter:description"}:
            return
        content = _plain_text(mapping.get("content", ""))
        if len(content) >= 20:
            self._description = content[:500]

    def text(self) -> str:
        return " ".join(self._chunks)

    def title(self) -> str | None:
        normalized = _plain_text(" ".join(self._title))
        return normalized[:200] if normalized else None

    def description(self) -> str | None:
        return self._description

    def headings(self) -> tuple[str, ...]:
        return tuple(self._headings)


def _validate_url(value: str) -> str:
    normalized = value.strip()
    parts = urlsplit(normalized)
    if parts.scheme not in {"http", "https"}:
        raise DeclaredProfileFetchFailed("profile URL must use HTTP or HTTPS")
    if parts.username or parts.password:
        raise DeclaredProfileFetchFailed("profile URL must not include credentials")
    if parts.hostname is None:
        raise DeclaredProfileFetchFailed("profile URL must include a hostname")
    host = unquote(parts.hostname).strip("[]")
    if not host:
        raise DeclaredProfileFetchFailed("profile URL must include a hostname")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DeclaredProfileFetchFailed("profile URL could not be resolved") from exc
    if not infos:
        raise DeclaredProfileFetchFailed("profile URL could not be resolved")
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise DeclaredProfileFetchFailed("profile URL resolved to an invalid address") from exc
        if not ip.is_global:
            raise DeclaredProfileFetchFailed("profile URL resolves to a blocked network")
    return normalized


def _allowed_content_type(value: str) -> bool:
    media_type = value.split(";", 1)[0].strip().casefold()
    return media_type in {"text/html", "text/plain", "application/xhtml+xml"}


def _is_html(value: str) -> bool:
    return value.split(";", 1)[0].strip().casefold() in {"text/html", "application/xhtml+xml"}


def _charset(value: str) -> str:
    match = re.search(r"charset=([A-Za-z0-9._-]+)", value, re.I)
    return match.group(1) if match else "utf-8"


def _plain_text(value: str) -> str:
    without_controls = "".join(
        character if ord(character) >= 32 or character in {"\n", "\r", "\t"} else " "
        for character in value
    )
    lines = [" ".join(line.split()) for line in without_controls.splitlines()]
    return "\n".join(line for line in lines if line)[:50_000]
