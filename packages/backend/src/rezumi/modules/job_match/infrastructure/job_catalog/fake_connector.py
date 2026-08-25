"""Deterministic job-catalog connector for local development and tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing

_FIXED_TIME = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


class FakeCatalogConnector:
    platform = "fake"

    async def iter_listings(self) -> AsyncIterator[CatalogJobListing]:
        yield CatalogJobListing(
            platform="fake",
            external_id="fake-1",
            title="Software Engineer",
            company="Fixture Co",
            location="Remote",
            remote=True,
            application_url="https://example.test/jobs/fake-1",
            source_text="Build and ship backend services. Python, PostgreSQL.",
            posted_at=_FIXED_TIME,
        )
        yield CatalogJobListing(
            platform="fake",
            external_id="fake-2",
            title="Product Designer",
            company="Fixture Co",
            location="Remote",
            remote=True,
            application_url="https://example.test/jobs/fake-2",
            source_text="Design flows for a career platform. Figma, user research.",
            posted_at=_FIXED_TIME,
        )
