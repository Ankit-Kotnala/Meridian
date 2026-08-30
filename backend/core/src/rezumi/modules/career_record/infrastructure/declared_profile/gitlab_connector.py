"""GitLab public profile connector using the documented REST API."""

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

_GITLAB_USER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
# GitLab site routes that occupy the same path shape as a namespace.
_RESERVED_PATHS = frozenset(
    {
        "dashboard",
        "explore",
        "help",
        "groups",
        "projects",
        "public",
        "search",
        "users",
        "-",
    }
)
_MAX_PROJECTS = 5
_TIMEOUT = 8.0


class GitlabDeclaredProfileConnector:
    """Reads a user's public GitLab profile (`gitlab.com/<user>`) via the v4 API."""

    platform = "gitlab"

    def supports(self, url: str) -> bool:
        return _username(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        username = _username(normalized)
        if username is None:
            raise DeclaredProfileFetchFailed("GitLab profile URL is not supported")
        return await asyncio.to_thread(self._fetch_sync, normalized, username)

    def _fetch_sync(self, profile_url: str, username: str) -> DeclaredProfileFetchResult:
        users = self._get_json(f"https://gitlab.com/api/v4/users?username={username}")
        if not isinstance(users, list) or not users or not isinstance(users[0], dict):
            raise DeclaredProfileFetchFailed("GitLab profile was not found")
        user = users[0]
        user_id = user.get("id")

        achievements: list[DeclaredProfileAchievement] = []
        bio = str(user.get("bio") or "").strip()
        name = str(user.get("name") or username).strip()

        projects: Any = []
        if isinstance(user_id, int):
            projects = self._get_json(
                f"https://gitlab.com/api/v4/users/{user_id}/projects"
                "?visibility=public&order_by=last_activity_at&per_page=5"
            )
        project_count = len(projects) if isinstance(projects, list) else 0

        if bio or project_count > 0:
            statement = bio or f"Public GitLab profile with {project_count} public projects."
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} on GitLab",
                    statement=statement,
                    source_url=profile_url,
                    excerpt=statement[:500],
                )
            )

        if isinstance(projects, list):
            for project in projects[:_MAX_PROJECTS]:
                if not isinstance(project, dict):
                    continue
                project_name = str(project.get("name") or "").strip()
                if not project_name:
                    continue
                description = str(project.get("description") or "").strip()
                stars = int(project.get("star_count") or 0)
                web_url = str(project.get("web_url") or profile_url)
                parts = [description] if description else []
                if stars > 0:
                    parts.append(f"{stars} public stars.")
                statement = " ".join(parts) or f"Public project {project_name}."
                achievements.append(
                    DeclaredProfileAchievement(
                        title=project_name,
                        statement=statement,
                        source_url=web_url,
                        excerpt=statement[:500],
                    )
                )

        if not achievements:
            raise DeclaredProfileFetchFailed("GitLab profile did not expose public achievements")

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=tuple(achievements),
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed GitLab API host
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(200_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("GitLab profile was not found") from exc
            raise DeclaredProfileFetchFailed("GitLab profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("GitLab profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))


def _username(url: str) -> str | None:
    """Return the top-level GitLab namespace a URL belongs to.

    A project link ("gitlab.com/alex/pipeline-kit") names the same account as
    the profile link, so it enriches from that account instead of being
    rejected; the API reports "not found" if the namespace is a group.
    """

    if not host_matches(hostname(url), "gitlab.com"):
        return None
    segments = path_segments(url)
    if not segments:
        return None
    candidate = segments[0]
    if candidate.casefold() in _RESERVED_PATHS:
        return None
    return candidate if _GITLAB_USER.match(candidate) else None
