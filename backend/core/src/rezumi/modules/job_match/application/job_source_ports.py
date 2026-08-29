"""Ports for published job-board and ATS listing connectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class JobSourceListing:
    external_id: str
    title: str
    company: str | None
    location: str | None
    application_url: str | None
    source_text: str


class JobSourceConnector(Protocol):
    platform: str

    async def fetch_listings(self, query: str) -> tuple[JobSourceListing, ...]: ...


class JobSourceConnectorRegistry(Protocol):
    def resolve(self, platform: str) -> JobSourceConnector: ...
