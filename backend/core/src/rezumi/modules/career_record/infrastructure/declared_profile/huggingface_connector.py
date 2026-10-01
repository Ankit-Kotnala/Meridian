"""Hugging Face public Hub profile connector.

The Hub exposes documented JSON endpoints for public models, datasets, and
Spaces. This connector imports only those published artefacts; it never
attempts to infer private activity or scrape the rendered profile page.
"""

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

_HANDLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_RESERVED_PATHS = frozenset(
    {
        "blog",
        "datasets",
        "docs",
        "evaluate",
        "login",
        "models",
        "organizations",
        "papers",
        "spaces",
        "tasks",
        "join",
    }
)
_MAX_ARTEFACTS = 5
_TIMEOUT = 8.0


class HuggingFaceDeclaredProfileConnector:
    """Read a user's public models, datasets, and Spaces from Hugging Face."""

    platform = "huggingface"

    def supports(self, url: str) -> bool:
        return _target(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        target = _target(normalized)
        if target is None:
            raise DeclaredProfileFetchFailed("Hugging Face profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, *target)

    def _fetch_sync(
        self,
        profile_url: str,
        username: str,
        repository_type: str | None,
        repository_name: str | None,
    ) -> DeclaredProfileFetchResult:
        achievements: list[DeclaredProfileAchievement] = []
        if repository_name is not None and repository_type is not None:
            artifact = self._get_artifact(username, repository_name, repository_type)
            if artifact is None:
                raise DeclaredProfileFetchFailed("Hugging Face repository was not found")
            achievement = _artifact_achievement(artifact, repository_type)
            if achievement is not None:
                achievements.append(achievement)
        else:
            for kind in ("model", "dataset", "space"):
                payload = self._get_optional_json(
                    f"https://huggingface.co/api/{kind}s?author={username}"
                    f"&limit={_MAX_ARTEFACTS}&sort=lastModified&direction=-1"
                )
                if not isinstance(payload, list):
                    continue
                for artifact in payload[:_MAX_ARTEFACTS]:
                    if not isinstance(artifact, dict):
                        continue
                    achievement = _artifact_achievement(artifact, kind)
                    if achievement is not None:
                        achievements.append(achievement)

        if not achievements:
            raise DeclaredProfileFetchFailed(
                "Hugging Face profile did not expose public models, datasets, or Spaces"
            )
        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=tuple(achievements),
        )

    def _get_artifact(self, username: str, name: str, kind: str) -> Any | None:
        payload = self._get_optional_json(f"https://huggingface.co/api/{kind}s/{username}/{name}")
        return payload if isinstance(payload, dict) else None

    def _get_optional_json(self, url: str) -> Any | None:
        request = Request(  # noqa: S310 - fixed Hugging Face API host
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
                return None
            raise DeclaredProfileFetchFailed("Hugging Face profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("Hugging Face profile could not be read") from exc


def _target(url: str) -> tuple[str, str | None, str | None] | None:
    if not host_matches(hostname(url), "huggingface.co"):
        return None
    segments = path_segments(url)
    if not segments:
        return None
    kind_prefix = segments[0].casefold()
    if kind_prefix in {"models", "datasets", "spaces"}:
        if len(segments) < 3:
            return None
        username, repository = segments[1], segments[2]
        kind = kind_prefix[:-1]
        return (username, kind, repository) if _HANDLE.match(username) else None
    if kind_prefix in _RESERVED_PATHS:
        return None
    username = segments[0]
    if not _HANDLE.match(username):
        return None
    if len(segments) < 2:
        return username, None, None
    return username, "model", segments[1]


def _artifact_achievement(artifact: dict[str, Any], kind: str) -> DeclaredProfileAchievement | None:
    identifier = str(artifact.get("id") or artifact.get("modelId") or "").strip()
    if not identifier:
        return None
    description = " ".join(str(artifact.get("description") or "").split())
    pipeline = str(artifact.get("pipeline_tag") or "").strip()
    library = str(artifact.get("library_name") or "").strip()
    downloads = artifact.get("downloads")
    likes = artifact.get("likes")
    parts = [description] if description else []
    if pipeline:
        parts.append(f"Task: {pipeline}.")
    if library:
        parts.append(f"Library: {library}.")
    downloads_count = positive_public_int(downloads)
    if downloads_count > 0:
        parts.append(f"{downloads_count} public downloads.")
    likes_count = positive_public_int(likes)
    if likes_count > 0:
        parts.append(f"{likes_count} public likes.")
    statement = " ".join(parts) or f"Public Hugging Face {kind} repository."
    return DeclaredProfileAchievement(
        title=identifier,
        statement=statement[:2_000],
        source_url=f"https://huggingface.co/{identifier}",
        excerpt=statement[:500],
    )
