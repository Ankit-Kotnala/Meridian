"""GitHub public profile connector using the documented REST and GraphQL APIs."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchFailed,
    DeclaredProfileFetchResult,
    hostname,
    normalize_declared_profile_url,
    path_segments,
)

_GITHUB_USER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_GITHUB_WEB_HOSTS = frozenset({"github.com", "gist.github.com"})
_SMART_APOSTROPHES = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "`": "'",
    }
)
# Site routes that look exactly like a username in a URL path. Treating one as
# a profile produces a confusing "profile was not found" instead of routing the
# link to the generic fallback.
_RESERVED_PATHS = frozenset(
    {
        "about",
        "apps",
        "collections",
        "contact",
        "customer-stories",
        "dashboard",
        "enterprise",
        "events",
        "explore",
        "features",
        "issues",
        "join",
        "login",
        "marketplace",
        "new",
        "notifications",
        "orgs",
        "organizations",
        "pricing",
        "pulls",
        "readme",
        "search",
        "security",
        "settings",
        "site",
        "sponsors",
        "topics",
        "trending",
        "users",
    }
)
# Second path segments that begin a repository sub-route, not a repo slug.
_REPO_ROUTE_MARKERS = frozenset(
    {
        "blob",
        "commit",
        "commits",
        "compare",
        "discussions",
        "graphs",
        "issues",
        "labels",
        "milestones",
        "network",
        "projects",
        "pull",
        "pulls",
        "pulse",
        "releases",
        "security",
        "settings",
        "stargazers",
        "tags",
        "tree",
        "wiki",
    }
)
_MAX_REPOS = 5
_MAX_TOPICS = 5
_MAX_PINNED_REPOS = 6
_MAX_ACTIVITY_REPOSITORIES = 6
_MAX_ORGANIZATIONS = 3
_MAX_README_EXCERPT = 600
_TIMEOUT = 8.0
_GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# Pinned repositories and a historical contribution collection are GraphQL-only
# fields. GitHub requires a token for its GraphQL API, so the connector keeps
# its public REST-only import useful when no deployment token is configured.
_PROFILE_OVERVIEW_QUERY = """
query RezumiGithubCandidateOverview($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    pinnedItems(first: 6, types: [REPOSITORY]) {
      nodes {
        ... on Repository {
          name
          nameWithOwner
          description
          url
          isFork
          isArchived
          stargazerCount
          primaryLanguage { name }
          repositoryTopics(first: 5) { nodes { topic { name } } }
          owner {
            login
            url
            ... on Organization { name description }
          }
        }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      commitContributionsByRepository(maxRepositories: 6) {
        repository {
          nameWithOwner
          url
          licenseInfo { spdxId }
          owner {
            __typename
            login
            url
            ... on Organization { name description }
          }
        }
        contributions { totalCount }
      }
      pullRequestContributionsByRepository(maxRepositories: 6) {
        repository {
          nameWithOwner
          url
          licenseInfo { spdxId }
          owner {
            __typename
            login
            url
            ... on Organization { name description }
          }
        }
        contributions { totalCount }
      }
      pullRequestReviewContributionsByRepository(maxRepositories: 6) {
        repository {
          nameWithOwner
          url
          licenseInfo { spdxId }
          owner {
            __typename
            login
            url
            ... on Organization { name description }
          }
        }
        contributions { totalCount }
      }
    }
  }
}
"""


class GithubDeclaredProfileConnector:
    platform = "github"

    def __init__(self, *, api_token: str | None = None) -> None:
        # A deployment-owned GitHub token only unlocks public profile fields
        # unavailable from REST. It is never put into an achievement, evidence
        # record, exception, or log message.
        self._api_token = api_token.strip() if api_token and api_token.strip() else None

    def supports(self, url: str) -> bool:
        return _github_target(normalize_declared_profile_url(url)) is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        target = _github_target(normalized)
        if target is None:
            raise DeclaredProfileFetchFailed("GitHub profile URL is not supported")
        username, repo_name = target
        return await asyncio.to_thread(self._fetch_sync, normalized, username, repo_name)

    def _fetch_sync(
        self,
        profile_url: str,
        username: str,
        repo_name: str | None,
    ) -> DeclaredProfileFetchResult:
        user = self._get_json(f"https://api.github.com/users/{username}")
        now = datetime.now(tz=UTC)
        achievements: list[DeclaredProfileAchievement] = []
        seen_repo_urls: set[str] = set()

        name = _normalize_public_text(str(user.get("name") or username))
        profile_html_url = str(user.get("html_url") or f"https://github.com/{username}")
        profile_achievements = self._profile_achievements(
            user,
            name=name,
            profile_html_url=profile_html_url,
        )

        if repo_name is not None:
            pinned = self._repo_achievement(username, repo_name)
            if pinned is not None:
                achievements.append(pinned)
                seen_repo_urls.add(pinned.source_url.casefold())
            else:
                achievements.extend(profile_achievements)
        else:
            profile_readme = self._profile_readme_achievement(
                username,
                name=name,
                profile_html_url=profile_html_url,
            )
            if profile_readme is not None:
                achievements.append(profile_readme)
            achievements.extend(profile_achievements)
            overview = self._profile_overview(username, now)
            pinned_repositories = self._pinned_repositories(overview)
            if pinned_repositories:
                for repo in pinned_repositories:
                    achievement = self._repository_achievement(
                        repo,
                        seen_repo_urls,
                        pinned=True,
                    )
                    if achievement is None:
                        continue
                    achievements.append(achievement)
                    seen_repo_urls.add(achievement.source_url.casefold())
            else:
                self._append_owned_repository_achievements(
                    username,
                    achievements,
                    seen_repo_urls,
                )
            achievements.extend(
                self._contribution_overview_achievements(
                    overview,
                    profile_html_url=profile_html_url,
                    year=now.year,
                )
            )

        if not achievements:
            raise DeclaredProfileFetchFailed("GitHub profile did not expose public achievements")

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=now,
            achievements=tuple(achievements),
        )

    def _profile_achievements(
        self,
        user: dict[str, Any],
        *,
        name: str,
        profile_html_url: str,
    ) -> list[DeclaredProfileAchievement]:
        achievements: list[DeclaredProfileAchievement] = []
        bio = _normalize_public_text(str(user.get("bio") or ""))
        if bio and not _is_role_tagline(bio):
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} on GitHub",
                    statement=bio,
                    source_url=profile_html_url,
                    excerpt=bio[:500],
                )
            )

        location = _normalize_public_text(str(user.get("location") or ""))
        if location:
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} — GitHub location",
                    statement=location,
                    source_url=profile_html_url,
                    excerpt=location[:500],
                )
            )

        company = _normalize_public_text(str(user.get("company") or ""))
        if company:
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} — GitHub company",
                    statement=company,
                    source_url=profile_html_url,
                    excerpt=company[:500],
                )
            )

        blog = _normalize_public_text(str(user.get("blog") or ""))
        if blog:
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"{name} — GitHub website",
                    statement=blog,
                    source_url=profile_html_url,
                    excerpt=blog[:500],
                )
            )
        return achievements

    def _repo_achievement(
        self,
        username: str,
        repo_name: str,
    ) -> DeclaredProfileAchievement | None:
        try:
            repo = self._get_json(f"https://api.github.com/repos/{username}/{repo_name}")
        except DeclaredProfileFetchFailed:
            return None
        if not isinstance(repo, dict):
            return None
        return self._repository_achievement(
            repo,
            set(),
            pinned=True,
        )

    def _append_owned_repository_achievements(
        self,
        username: str,
        achievements: list[DeclaredProfileAchievement],
        seen_repo_urls: set[str],
    ) -> None:
        """Keep the REST-only import useful when GraphQL is not configured."""

        repos = self._get_json(
            f"https://api.github.com/users/{username}/repos"
            "?sort=stars&direction=desc&per_page=30&type=owner"
        )
        if not isinstance(repos, list):
            return
        imported = 0
        for repo in repos:
            if imported >= _MAX_REPOS:
                break
            if not isinstance(repo, dict):
                continue
            achievement = self._repository_achievement(
                repo,
                seen_repo_urls,
            )
            if achievement is None:
                continue
            achievements.append(achievement)
            seen_repo_urls.add(achievement.source_url.casefold())
            imported += 1

    def _profile_readme_achievement(
        self,
        username: str,
        *,
        name: str,
        profile_html_url: str,
    ) -> DeclaredProfileAchievement | None:
        payload = self._get_optional_json(
            f"https://api.github.com/repos/{username}/{username}/readme"
        )
        excerpt = _readme_excerpt(payload)
        if excerpt is None:
            return None
        source_url = _readme_source_url(payload, f"https://github.com/{username}/{username}")
        statement = f"Public profile README: {excerpt}"
        return DeclaredProfileAchievement(
            title=f"{name} — GitHub profile README",
            statement=statement,
            source_url=source_url or profile_html_url,
            excerpt=statement[:500],
        )

    def _repository_readme_excerpt(self, repo: dict[str, Any]) -> str | None:
        owner_login = str((repo.get("owner") or {}).get("login") or "").strip()
        repo_name = str(repo.get("name") or "").strip()
        if not owner_login or not repo_name:
            return None
        payload = self._get_optional_json(
            f"https://api.github.com/repos/{owner_login}/{repo_name}/readme"
        )
        return _readme_excerpt(payload)

    def _repository_achievement(
        self,
        repo: dict[str, Any],
        seen_repo_urls: set[str],
        *,
        pinned: bool = False,
    ) -> DeclaredProfileAchievement | None:
        """Read a project README only after the repository passes relevance checks."""

        base = self._achievement_from_repo(repo, seen_repo_urls, pinned=pinned)
        if base is None:
            return None
        readme_excerpt = self._repository_readme_excerpt(repo)
        if readme_excerpt is None:
            return base
        return self._achievement_from_repo(
            repo,
            seen_repo_urls,
            pinned=pinned,
            readme_excerpt=readme_excerpt,
        )

    def _profile_overview(
        self,
        username: str,
        now: datetime,
    ) -> dict[str, Any] | None:
        if self._api_token is None:
            return None
        from_value = f"{now.year}-01-01T00:00:00Z"
        to_value = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = self._post_graphql(
            _PROFILE_OVERVIEW_QUERY,
            {"login": username, "from": from_value, "to": to_value},
        )
        if not isinstance(payload, dict):
            return None
        data = payload.get("data")
        user = data.get("user") if isinstance(data, dict) else None
        return user if isinstance(user, dict) else None

    def _pinned_repositories(self, overview: dict[str, Any] | None) -> list[dict[str, Any]]:
        if overview is None:
            return []
        pinned = overview.get("pinnedItems")
        nodes = pinned.get("nodes") if isinstance(pinned, dict) else None
        if not isinstance(nodes, list):
            return []
        repositories: list[dict[str, Any]] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            repository = _rest_repository_from_graphql(node)
            if repository is not None:
                repositories.append(repository)
        return repositories[:_MAX_PINNED_REPOS]

    def _contribution_overview_achievements(
        self,
        overview: dict[str, Any] | None,
        *,
        profile_html_url: str,
        year: int,
    ) -> list[DeclaredProfileAchievement]:
        if overview is None:
            return []
        collection = overview.get("contributionsCollection")
        if not isinstance(collection, dict):
            return []
        calendar = collection.get("contributionCalendar")
        calendar_total = calendar.get("totalContributions") if isinstance(calendar, dict) else 0
        total = _positive_int(calendar_total)
        achievements: list[DeclaredProfileAchievement] = []
        if total > 0:
            details = _contribution_details(collection)
            contribution_label = "contribution" if total == 1 else "contributions"
            statement = f"GitHub reports {total} public {contribution_label} in {year}"
            if details:
                statement += f" ({', '.join(details)})."
            else:
                statement += "."
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"GitHub — {year} public contribution overview",
                    statement=statement,
                    source_url=profile_html_url,
                    excerpt=statement[:500],
                )
            )
        achievements.extend(self._organization_activity_achievements(collection, year))
        return achievements

    def _organization_activity_achievements(
        self,
        collection: dict[str, Any],
        year: int,
    ) -> list[DeclaredProfileAchievement]:
        organizations: dict[str, dict[str, Any]] = {}
        for key in (
            "commitContributionsByRepository",
            "pullRequestContributionsByRepository",
            "pullRequestReviewContributionsByRepository",
        ):
            entries = collection.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries[:_MAX_ACTIVITY_REPOSITORIES]:
                if not isinstance(entry, dict):
                    continue
                repository = entry.get("repository")
                if not isinstance(repository, dict) or not _is_licensed_repository(repository):
                    continue
                owner = repository.get("owner")
                if not isinstance(owner, dict) or owner.get("__typename") != "Organization":
                    continue
                login = _normalize_public_text(str(owner.get("login") or ""))
                if not login:
                    continue
                contribution_count = _positive_int(
                    (entry.get("contributions") or {}).get("totalCount")
                    if isinstance(entry.get("contributions"), dict)
                    else 0
                )
                if contribution_count == 0:
                    continue
                aggregate = organizations.setdefault(
                    login.casefold(),
                    {
                        "count": 0,
                        "description": _normalize_public_text(str(owner.get("description") or "")),
                        "login": login,
                        "repositories": [],
                        "source_url": str(owner.get("url") or repository.get("url") or "").strip(),
                    },
                )
                aggregate["count"] += contribution_count
                repository_name = _normalize_public_text(str(repository.get("nameWithOwner") or ""))
                if repository_name and repository_name not in aggregate["repositories"]:
                    aggregate["repositories"].append(repository_name)

        achievements: list[DeclaredProfileAchievement] = []
        for organization in sorted(
            organizations.values(),
            key=lambda item: (-int(item["count"]), str(item["login"]).casefold()),
        )[:_MAX_ORGANIZATIONS]:
            repositories = ", ".join(organization["repositories"][:3])
            statement = (
                f"{organization['count']} recorded public contribution"
                f"{'s' if organization['count'] != 1 else ''} in {year} to licensed repositories"
            )
            if repositories:
                statement += f": {repositories}."
            else:
                statement += "."
            description = str(organization["description"])
            if description:
                statement += f" Organization overview: {description}"
            source_url = str(organization["source_url"])
            if not source_url:
                continue
            achievements.append(
                DeclaredProfileAchievement(
                    title=f"Open-source activity — {organization['login']}",
                    statement=statement,
                    source_url=source_url,
                    excerpt=statement[:500],
                )
            )
        return achievements

    def _achievement_from_repo(
        self,
        repo: dict[str, Any],
        seen_repo_urls: set[str],
        *,
        pinned: bool = False,
        readme_excerpt: str | None = None,
    ) -> DeclaredProfileAchievement | None:
        if not pinned and (repo.get("fork") or repo.get("archived")):
            return None
        repo_name = str(repo.get("name") or "").strip()
        if not repo_name:
            return None
        html_url = str(repo.get("html_url") or "").strip()
        if html_url and html_url.casefold() in seen_repo_urls:
            return None
        description = _normalize_public_text(str(repo.get("description") or ""))
        language = _normalize_public_text(str(repo.get("language") or ""))
        stars = int(repo.get("stargazers_count") or 0)
        owner_login = str((repo.get("owner") or {}).get("login") or "").strip()
        topics = [
            _normalize_public_text(str(topic))
            for topic in (repo.get("topics") or [])
            if str(topic).strip()
        ]
        if not pinned and not description and stars == 0:
            return None
        parts = [description] if description else []
        if readme_excerpt:
            parts.append(f"README highlights: {readme_excerpt}")
        if language:
            parts.append(f"Primary language: {language}.")
        if stars > 0:
            parts.append(f"{stars} public stars.")
        if topics:
            parts.append(f"Topics: {', '.join(topics[:_MAX_TOPICS])}.")
        statement = " ".join(parts)[:2_000] or f"Public repository {repo_name}."
        title = f"{owner_login}/{repo_name}" if owner_login else repo_name
        return DeclaredProfileAchievement(
            title=title,
            statement=statement,
            source_url=html_url or f"https://github.com/{repo_name}",
            excerpt=statement[:500],
        )

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed GitHub API host
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(200_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("GitHub profile was not found") from exc
            if exc.code in {403, 429}:
                raise DeclaredProfileFetchFailed(
                    "GitHub is rate-limiting public profile reads right now. Try again later."
                ) from exc
            raise DeclaredProfileFetchFailed("GitHub profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("GitHub profile could not be read") from exc
        return json.loads(payload.decode("utf-8"))

    def _get_optional_json(self, url: str) -> Any | None:
        """Read supplemental public data without failing the whole import."""

        request = Request(  # noqa: S310 - fixed GitHub API host
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(200_000)
            return json.loads(payload.decode("utf-8"))
        except (HTTPError, TimeoutError, URLError, OSError, json.JSONDecodeError):
            return None

    def _post_graphql(self, query: str, variables: dict[str, str]) -> Any | None:
        if self._api_token is None:
            return None
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = Request(  # noqa: S310 - fixed GitHub GraphQL endpoint
            _GITHUB_GRAPHQL_URL,
            data=body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = json.loads(response.read(200_000).decode("utf-8"))
        except (HTTPError, TimeoutError, URLError, OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("errors"):
            return None
        return payload


def _github_target(url: str) -> tuple[str, str | None] | None:
    """Return the GitHub account and optional repository named by ``url``."""

    if not _is_github_web_host(hostname(url)):
        return None
    segments = path_segments(url)
    if not segments:
        return None

    if segments[0].casefold() == "users":
        if len(segments) < 2:
            return None
        username = segments[1]
        if username.casefold() in _RESERVED_PATHS:
            return None
        return (username, None) if _GITHUB_USER.match(username) else None

    username = segments[0]
    if username.casefold() in _RESERVED_PATHS:
        return None
    if not _GITHUB_USER.match(username):
        return None

    repo_name = None
    if len(segments) >= 2 and segments[1].casefold() not in _REPO_ROUTE_MARKERS:
        repo_name = segments[1]
    return username, repo_name


def _is_github_web_host(host: str) -> bool:
    normalized = host.casefold().rstrip(".").removeprefix("www.")
    return normalized in _GITHUB_WEB_HOSTS


def _normalize_public_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    return unicodedata.normalize("NFKC", normalized.translate(_SMART_APOSTROPHES))


def _is_role_tagline(value: str) -> bool:
    if "|" not in value:
        return False
    segments = [segment.strip() for segment in value.split("|") if segment.strip()]
    if len(segments) < 2:
        return False
    return all(
        len(segment.split()) <= 5 and not any(char in segment for char in ".!?")
        for segment in segments
    )


def _readme_excerpt(payload: Any) -> str | None:
    """Return a bounded, text-only public README excerpt.

    The README is evidence supplied by a third-party profile, not an instruction
    source. It is decoded as data, stripped to readable prose, and kept short
    enough for an owner to review in the achievement draft and evidence item.
    """

    if not isinstance(payload, dict):
        return None
    if str(payload.get("encoding") or "").casefold() != "base64":
        return None
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        decoded = base64.b64decode(content.encode("ascii"), validate=False).decode(
            "utf-8", errors="replace"
        )
    except (binascii.Error, UnicodeEncodeError, ValueError):
        return None

    lines: list[str] = []
    in_code_block = False
    for raw_line in decoded.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line or line.startswith("<!--"):
            continue
        if line.startswith(("![", "[![", "<img", "<picture", "</picture")):
            continue
        line = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"^[#>*\-\d.\s]+", "", line)
        line = re.sub(r"[`_~]", "", line)
        normalized = _normalize_public_text(line)
        if len(normalized) >= 12:
            lines.append(normalized)
        if len(" ".join(lines)) >= _MAX_README_EXCERPT:
            break
    excerpt = _normalize_public_text(" ".join(lines))[:_MAX_README_EXCERPT]
    return excerpt or None


def _readme_source_url(payload: Any, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback
    value = str(payload.get("html_url") or payload.get("download_url") or "").strip()
    return value or fallback


def _rest_repository_from_graphql(node: dict[str, Any]) -> dict[str, Any] | None:
    name = _normalize_public_text(str(node.get("name") or ""))
    url = str(node.get("url") or "").strip()
    owner = node.get("owner")
    if not name or not url or not isinstance(owner, dict):
        return None
    owner_login = _normalize_public_text(str(owner.get("login") or ""))
    if not owner_login:
        return None
    primary_language = node.get("primaryLanguage")
    topics = node.get("repositoryTopics")
    raw_topic_nodes = topics.get("nodes") if isinstance(topics, dict) else []
    topic_nodes = raw_topic_nodes if isinstance(raw_topic_nodes, list) else []
    topic_names = [
        _normalize_public_text(str(item.get("topic", {}).get("name") or ""))
        for item in topic_nodes
        if isinstance(item, dict) and isinstance(item.get("topic"), dict)
    ]
    return {
        "name": name,
        "description": node.get("description"),
        "html_url": url,
        "fork": node.get("isFork") is True,
        "archived": node.get("isArchived") is True,
        "language": primary_language.get("name") if isinstance(primary_language, dict) else None,
        "stargazers_count": _positive_int(node.get("stargazerCount")),
        "topics": [topic for topic in topic_names if topic],
        "owner": {"login": owner_login},
    }


def _positive_int(value: Any) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def _contribution_details(collection: dict[str, Any]) -> list[str]:
    fields = (
        ("totalCommitContributions", "commits"),
        ("totalPullRequestContributions", "pull requests"),
        ("totalIssueContributions", "issues"),
        ("totalPullRequestReviewContributions", "pull request reviews"),
    )
    return [
        f"{count} {label}"
        for field, label in fields
        if (count := _positive_int(collection.get(field))) > 0
    ]


def _is_licensed_repository(repository: dict[str, Any]) -> bool:
    license_info = repository.get("licenseInfo")
    if not isinstance(license_info, dict):
        return False
    spdx_id = str(license_info.get("spdxId") or "").strip().upper()
    return bool(spdx_id and spdx_id != "NOASSERTION")


def _username(url: str) -> str | None:
    """Return the account a GitHub URL belongs to, profile or repository."""

    target = _github_target(url)
    return target[0] if target is not None else None
