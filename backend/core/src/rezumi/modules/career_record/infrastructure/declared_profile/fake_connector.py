"""Deterministic declared-profile connector for local development and tests."""

from __future__ import annotations

from datetime import UTC, datetime

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchResult,
    normalize_declared_profile_url,
)


class FakeDeclaredProfileConnector:
    platform = "fake"

    def supports(self, url: str) -> bool:
        return "example.test/profile" in normalize_declared_profile_url(url)

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        now = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=normalized,
            fetched_at=now,
            achievements=(
                DeclaredProfileAchievement(
                    title="Open-source maintainer",
                    statement="Maintains a public portfolio with two shipped projects.",
                    source_url=normalized,
                    excerpt="Maintains a public portfolio with two shipped projects.",
                ),
                DeclaredProfileAchievement(
                    title="Conference speaker",
                    statement="Presented engineering practices at a regional meetup.",
                    source_url=f"{normalized}#talks",
                    excerpt="Presented engineering practices at a regional meetup.",
                ),
            ),
        )
