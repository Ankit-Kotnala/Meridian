"""SSRF-aware HTTP(S) job posting importer."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from careeros.modules.job_match.application import ImportedJobSource
from careeros.modules.job_match.domain import JobImportRejected


class _HeaderMapping(Protocol):
    def get(self, name: str, default: str | None = None) -> str: ...


class _ReadableResponse(Protocol):
    headers: _HeaderMapping

    def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class UrlImportOptions:
    max_bytes: int = 250_000
    timeout_seconds: float = 6.0
    max_redirects: int = 5

    def __post_init__(self) -> None:
        if self.max_bytes < 20 or self.timeout_seconds <= 0 or self.max_redirects < 0:
            raise ValueError("URL import limits are invalid")


class SafeUrlJobImportProvider:
    """Fetch bounded job posting text from public HTTP(S) URLs."""

    def __init__(self, options: UrlImportOptions | None = None) -> None:
        self._options = options or UrlImportOptions()
        self._opener = build_opener(_NoRedirect)

    async def fetch(self, url: str) -> ImportedJobSource:
        return await asyncio.to_thread(self._fetch_sync, url)

    def _fetch_sync(self, url: str) -> ImportedJobSource:
        current = _validate_url(url)
        for _ in range(self._options.max_redirects + 1):
            request = Request(  # noqa: S310 - current is validated before every request.
                current,
                headers={
                    "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
                    "User-Agent": "CareerOSJobImporter/1.0",
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
                        raise JobImportRejected("redirect missing location") from exc
                    current = _validate_url(urljoin(current, location))
                    continue
                raise JobImportRejected("remote job posting could not be read") from exc
            except (TimeoutError, URLError, OSError) as exc:
                raise JobImportRejected("remote job posting could not be read") from exc
        raise JobImportRejected("too many redirects while importing job posting")

    def _read_response(self, final_url: str, response: _ReadableResponse) -> ImportedJobSource:
        headers = response.headers
        content_type = headers.get("Content-Type", "text/plain")
        if not _allowed_content_type(content_type):
            raise JobImportRejected("unsupported job posting content type")
        payload = response.read(self._options.max_bytes + 1)
        if len(payload) > self._options.max_bytes:
            raise JobImportRejected("remote job posting is too large")
        charset = _charset(content_type)
        decoded = payload.decode(charset, errors="replace")
        if _is_html(content_type):
            parser = _TextExtractor()
            parser.feed(decoded)
            parser.close()
            text = parser.text()
            title = parser.title()
        else:
            text = decoded
            title = None
        normalized = _plain_text(text)
        if len(normalized) < 20:
            raise JobImportRejected("remote job posting did not contain usable text")
        return ImportedJobSource(final_url=final_url, source_text=normalized, title=title)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._title_depth = 0
        self._chunks: list[str] = []
        self._title: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript", "template"}:
            self._skip_depth += 1
        if lowered == "title":
            self._title_depth += 1
        if lowered in {"br", "p", "div", "section", "article", "li", "tr", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript", "template"} and self._skip_depth:
            self._skip_depth -= 1
        if lowered == "title" and self._title_depth:
            self._title_depth -= 1
        if lowered in {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._title_depth:
            self._title.append(data)
        self._chunks.append(data)

    def text(self) -> str:
        return " ".join(self._chunks)

    def title(self) -> str | None:
        normalized = _plain_text(" ".join(self._title))
        return normalized[:200] if normalized else None


def _validate_url(value: str) -> str:
    normalized = value.strip()
    parts = urlsplit(normalized)
    if parts.scheme not in {"http", "https"}:
        raise JobImportRejected("job import URL must use HTTP or HTTPS")
    if parts.username or parts.password:
        raise JobImportRejected("job import URL must not include credentials")
    if parts.hostname is None:
        raise JobImportRejected("job import URL must include a hostname")
    host = unquote(parts.hostname).strip("[]")
    if not host:
        raise JobImportRejected("job import URL must include a hostname")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise JobImportRejected("job import URL could not be resolved") from exc
    if not infos:
        raise JobImportRejected("job import URL could not be resolved")
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise JobImportRejected("job import URL resolved to an invalid address") from exc
        if not ip.is_global:
            raise JobImportRejected("job import URL resolves to a blocked network")
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
