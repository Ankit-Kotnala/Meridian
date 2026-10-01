"""Docker Hub public namespace connector using the documented Hub API."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchFailed,
    DeclaredProfileFetchResult,
    host_matches,
    hostname,
    normalize_declared_profile_url,
    path_segments,
)
from rezumi.modules.career_record.infrastructure.declared_profile.normalization import (
    positive_public_int,
)

_NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,254}$", re.IGNORECASE)
_RESERVED_PATHS = frozenset({"explore", "search", "signup", "login", "settings"})
_MAX_REPOSITORIES = 5
_TIMEOUT = 8.0


class DockerHubDeclaredProfileConnector:
    """Read public repositories published under a Docker Hub namespace."""

    platform = "dockerhub"

    def supports(self, url: str) -> bool:
        return _target(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        target = _target(normalized)
        if target is None:
            raise DeclaredProfileFetchFailed("Docker Hub profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, *target)

    def _fetch_sync(
        self, profile_url: str, namespace: str, repository: str | None
    ) -> DeclaredProfileFetchResult:
        repositories: list[Any]
        if repository is not None:
            payload = self._get_json(
                f"https://hub.docker.com/v2/namespaces/{namespace}/repositories/{repository}"
            )
            repositories = [payload] if isinstance(payload, dict) else []
        else:
            payload = self._get_json(
                f"https://hub.docker.com/v2/namespaces/{namespace}/repositories"
                f"?page_size={_MAX_REPOSITORIES}&ordering=last_updated"
            )
            values = payload.get("results") if isinstance(payload, dict) else None
            repositories = values if isinstance(values, list) else []

        achievements: list[DeclaredProfileAchievement] = []
        for item in repositories[:_MAX_REPOSITORIES]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            description = " ".join(str(item.get("description") or "").split())
            pulls = item.get("pull_count")
            stars = item.get("star_count")
            parts = [description] if description else []
            pulls_count = positive_public_int(pulls)
            if pulls_count > 0:
                parts.append(f"{pulls_count} public pulls.")
            stars_count = positive_public_int(stars)
            if stars_count > 0:
                parts.append(f"{stars_count} public stars.")
            statement = " ".join(parts) or "Public Docker image repository."
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{namespace}/{name}",
                    statement=statement[:2_000],
                    source_url=f"https://hub.docker.com/r/{namespace}/{name}",
                    excerpt=statement[:500],
                )
            )

        if not achievements:
            raise DeclaredProfileFetchFailed(
                "Docker Hub namespace did not expose public repositories"
            )
        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=tuple(achievements),
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed Docker Hub API host
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                return json.loads(response.read(400_000).decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("Docker Hub namespace was not found") from exc
            raise DeclaredProfileFetchFailed("Docker Hub profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("Docker Hub profile could not be read") from exc


def _target(url: str) -> tuple[str, str | None] | None:
    if not host_matches(hostname(url), "hub.docker.com"):
        return None
    segments = path_segments(url)
    if not segments:
        return None
    if segments[0].casefold() in {"u", "r"}:
        segments = segments[1:]
    if not segments or segments[0].casefold() in _RESERVED_PATHS:
        return None
    namespace = segments[0]
    if not _NAMESPACE.match(namespace):
        return None
    repository = segments[1] if len(segments) > 1 and _NAMESPACE.match(segments[1]) else None
    return namespace, repository
