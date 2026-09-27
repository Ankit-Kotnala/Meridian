"""Unit tests for the new declared-profile connectors (GitLab, Bitbucket,
Stack Overflow, Codeforces, dev.to, ORCID) and their registry wiring."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import Any
from unittest.mock import patch
from urllib.request import Request

import pytest

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileFetchFailed,
)
from rezumi.modules.career_record.infrastructure.declared_profile.bitbucket_connector import (
    BitbucketDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.codeforces_connector import (
    CodeforcesDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.devto_connector import (
    DevToDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.github_connector import (
    GithubDeclaredProfileConnector,
    _github_target,
)
from rezumi.modules.career_record.infrastructure.declared_profile.gitlab_connector import (
    GitlabDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.orcid_connector import (
    OrcidDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.portfolio_connector import (
    PortfolioDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.registry import (
    default_declared_profile_registry,
)
from rezumi.modules.career_record.infrastructure.declared_profile.stackexchange_connector import (
    StackExchangeDeclaredProfileConnector,
)


class _FakeJsonResponse:
    def __init__(self, payload: Any) -> None:
        self._buffer = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, _size: int) -> bytes:
        return self._buffer.read()

    def __enter__(self) -> _FakeJsonResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


# --- GitHub -------------------------------------------------------------


def test_github_target_supports_profile_repo_and_users_urls() -> None:
    assert _github_target("https://github.com/alex-example") == ("alex-example", None)
    assert _github_target("https://github.com/alex-example/rezumi") == (
        "alex-example",
        "rezumi",
    )
    assert _github_target("https://github.com/users/alex-example") == (
        "alex-example",
        None,
    )
    assert _github_target("https://gist.github.com/alex-example") == (
        "alex-example",
        None,
    )
    assert _github_target("https://api.github.com/users/alex-example") is None
    assert (
        _github_target("https://raw.githubusercontent.com/alex-example/rezumi/main/README.md")
        is None
    )


def test_github_connector_supports_user_urls() -> None:
    connector = GithubDeclaredProfileConnector()
    assert connector.supports("https://github.com/alex-example")
    assert connector.supports("https://github.com/alex-example/rezumi")
    assert connector.supports("https://github.com/users/alex-example")
    assert not connector.supports("https://api.github.com/users/alex-example")


@pytest.mark.asyncio
async def test_github_connector_prioritizes_linked_repository() -> None:
    connector = GithubDeclaredProfileConnector()
    responses = [
        _FakeJsonResponse(
            {"name": "Alex Example", "bio": "", "html_url": "https://github.com/alex-example"}
        ),
        _FakeJsonResponse(
            {
                "name": "rezumi",
                "description": "Career operating system",
                "language": "Python",
                "stargazers_count": 12,
                "html_url": "https://github.com/alex-example/rezumi",
                "owner": {"login": "alex-example"},
                "fork": False,
                "archived": False,
            }
        ),
        _FakeJsonResponse({}),
    ]

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.github_connector.urlopen",
        side_effect=responses,
    ):
        result = await connector.fetch("https://github.com/alex-example/rezumi")

    assert result.platform == "github"
    assert len(result.achievements) == 1
    assert result.achievements[0].title == "alex-example/rezumi"
    assert "Career operating system" in result.achievements[0].statement


@pytest.mark.asyncio
async def test_github_connector_filters_fork_and_empty_repos_for_profiles() -> None:
    connector = GithubDeclaredProfileConnector()
    responses = [
        _FakeJsonResponse(
            {
                "name": "Alex Example",
                "bio": "Platform engineer",
                "html_url": "https://github.com/alex-example",
            }
        ),
        _FakeJsonResponse({}),
        _FakeJsonResponse(
            [
                {
                    "name": "dotfiles",
                    "description": "",
                    "stargazers_count": 0,
                    "html_url": "https://github.com/alex-example/dotfiles",
                    "owner": {"login": "alex-example"},
                    "fork": False,
                    "archived": False,
                },
                {
                    "name": "infra-tools",
                    "description": "Deployment tooling",
                    "stargazers_count": 3,
                    "html_url": "https://github.com/alex-example/infra-tools",
                    "owner": {"login": "alex-example"},
                    "fork": False,
                    "archived": False,
                },
                {
                    "name": "upstream-clone",
                    "description": "Should be skipped",
                    "stargazers_count": 99,
                    "html_url": "https://github.com/alex-example/upstream-clone",
                    "owner": {"login": "alex-example"},
                    "fork": True,
                    "archived": False,
                },
            ]
        ),
        _FakeJsonResponse({}),
    ]

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.github_connector.urlopen",
        side_effect=responses,
    ):
        result = await connector.fetch("https://github.com/alex-example")

    assert result.achievements[0].statement == "Platform engineer"
    assert [item.title for item in result.achievements[1:]] == ["alex-example/infra-tools"]


@pytest.mark.asyncio
async def test_github_connector_imports_profile_fields_and_skips_role_taglines() -> None:
    connector = GithubDeclaredProfileConnector()
    responses = [
        _FakeJsonResponse(
            {
                "name": "Alex Example",
                "bio": "Software Engineer | Footballer",
                "location": "Berlin",
                "company": "Example GmbH",
                "blog": "https://alex.dev",
                "html_url": "https://github.com/alex-example",
            }
        ),
        _FakeJsonResponse({}),
        _FakeJsonResponse([]),
    ]

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.github_connector.urlopen",
        side_effect=responses,
    ):
        result = await connector.fetch("https://github.com/alex-example")

    statements = [item.statement for item in result.achievements]
    assert "Software Engineer | Footballer" not in statements
    assert "Berlin" in statements
    assert "Example GmbH" in statements
    assert "https://alex.dev" in statements


@pytest.mark.asyncio
async def test_github_connector_requests_star_sorted_owned_repositories() -> None:
    connector = GithubDeclaredProfileConnector()
    requested_urls: list[str] = []

    def _fake_urlopen(request: Request, timeout: float = 0) -> _FakeJsonResponse:
        requested_urls.append(request.full_url)
        if request.full_url.endswith("/users/alex-example"):
            return _FakeJsonResponse(
                {
                    "name": "Alex Example",
                    "bio": "Platform engineer",
                    "html_url": "https://github.com/alex-example",
                }
            )
        return _FakeJsonResponse([])

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.github_connector.urlopen",
        side_effect=_fake_urlopen,
    ):
        await connector.fetch("https://github.com/alex-example")

    assert any("sort=stars" in url and "type=owner" in url for url in requested_urls)


@pytest.mark.asyncio
async def test_github_connector_imports_profile_readme_pinned_projects_and_public_activity() -> (
    None
):
    test_token = base64.b64decode(b"dGVzdC10b2tlbg==").decode("ascii")
    connector = GithubDeclaredProfileConnector(api_token=test_token)
    requested_urls: list[str] = []

    def _readme(text: str, url: str) -> _FakeJsonResponse:
        return _FakeJsonResponse(
            {
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                "encoding": "base64",
                "html_url": url,
            }
        )

    def _fake_urlopen(request: Request, timeout: float = 0) -> _FakeJsonResponse:
        _ = timeout
        requested_urls.append(request.full_url)
        if request.full_url.endswith("/users/alex-example"):
            return _FakeJsonResponse(
                {"name": "Alex Example", "bio": "", "html_url": "https://github.com/alex-example"}
            )
        if request.full_url.endswith("/repos/alex-example/alex-example/readme"):
            return _readme(
                "# Alex\n\nBuilding reliable developer tooling and public projects.",
                "https://github.com/alex-example/alex-example/blob/main/README.md",
            )
        if request.full_url == "https://api.github.com/graphql":
            assert request.get_method() == "POST"
            assert request.get_header("Authorization") == f"Bearer {test_token}"
            payload = json.loads(request.data.decode("utf-8"))
            assert payload["variables"]["login"] == "alex-example"
            return _FakeJsonResponse(
                {
                    "data": {
                        "user": {
                            "pinnedItems": {
                                "nodes": [
                                    {
                                        "name": "profile-project",
                                        "nameWithOwner": "alex-example/profile-project",
                                        "description": "A public project",
                                        "url": "https://github.com/alex-example/profile-project",
                                        "isFork": False,
                                        "isArchived": False,
                                        "stargazerCount": 7,
                                        "primaryLanguage": {"name": "Python"},
                                        "repositoryTopics": {
                                            "nodes": [{"topic": {"name": "automation"}}]
                                        },
                                        "owner": {
                                            "login": "alex-example",
                                            "url": "https://github.com/alex-example",
                                        },
                                    },
                                    {
                                        "name": "opensource-tool",
                                        "nameWithOwner": "open-source-labs/opensource-tool",
                                        "description": "A community-maintained tool",
                                        "url": "https://github.com/open-source-labs/opensource-tool",
                                        "isFork": False,
                                        "isArchived": False,
                                        "stargazerCount": 3,
                                        "primaryLanguage": {"name": "Go"},
                                        "repositoryTopics": {"nodes": []},
                                        "owner": {
                                            "login": "open-source-labs",
                                            "url": "https://github.com/open-source-labs",
                                        },
                                    },
                                ]
                            },
                            "contributionsCollection": {
                                "contributionCalendar": {"totalContributions": 24},
                                "totalCommitContributions": 12,
                                "totalIssueContributions": 2,
                                "totalPullRequestContributions": 7,
                                "totalPullRequestReviewContributions": 3,
                                "commitContributionsByRepository": [
                                    {
                                        "repository": {
                                            "nameWithOwner": "open-source-labs/opensource-tool",
                                            "url": "https://github.com/open-source-labs/opensource-tool",
                                            "licenseInfo": {"spdxId": "MIT"},
                                            "owner": {
                                                "__typename": "Organization",
                                                "login": "open-source-labs",
                                                "url": "https://github.com/open-source-labs",
                                                "name": "Open Source Labs",
                                                "description": (
                                                    "Maintains useful public developer tools."
                                                ),
                                            },
                                        },
                                        "contributions": {"totalCount": 12},
                                    }
                                ],
                                "pullRequestContributionsByRepository": [
                                    {
                                        "repository": {
                                            "nameWithOwner": "open-source-labs/opensource-tool",
                                            "url": "https://github.com/open-source-labs/opensource-tool",
                                            "licenseInfo": {"spdxId": "MIT"},
                                            "owner": {
                                                "__typename": "Organization",
                                                "login": "open-source-labs",
                                                "url": "https://github.com/open-source-labs",
                                                "name": "Open Source Labs",
                                                "description": (
                                                    "Maintains useful public developer tools."
                                                ),
                                            },
                                        },
                                        "contributions": {"totalCount": 7},
                                    }
                                ],
                                "pullRequestReviewContributionsByRepository": [],
                            },
                        }
                    }
                }
            )
        if request.full_url.endswith("/repos/alex-example/profile-project/readme"):
            return _readme(
                "Automates safe release checks for Python services.",
                "https://github.com/alex-example/profile-project/blob/main/README.md",
            )
        if request.full_url.endswith("/repos/open-source-labs/opensource-tool/readme"):
            return _readme(
                "CLI tooling maintained with the open-source community.",
                "https://github.com/open-source-labs/opensource-tool/blob/main/README.md",
            )
        raise AssertionError(f"Unexpected GitHub request: {request.full_url}")

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.github_connector.urlopen",
        side_effect=_fake_urlopen,
    ):
        result = await connector.fetch("https://github.com/alex-example")

    titles = [achievement.title for achievement in result.achievements]
    assert "Alex Example — GitHub profile README" in titles
    assert "alex-example/profile-project" in titles
    assert "open-source-labs/opensource-tool" in titles
    assert any("public contribution overview" in title for title in titles)
    assert "Open-source activity — open-source-labs" in titles
    assert not any("/users/alex-example/repos" in url for url in requested_urls)
    open_source = next(item for item in result.achievements if item.title.startswith("Open-source"))
    assert (
        "Organization overview: Maintains useful public developer tools." in open_source.statement
    )


# --- GitLab -------------------------------------------------------------


def test_gitlab_connector_supports_user_urls() -> None:
    connector = GitlabDeclaredProfileConnector()
    assert connector.supports("https://gitlab.com/alex-example")
    assert not connector.supports("https://github.com/alex")


@pytest.mark.asyncio
async def test_gitlab_connector_extracts_bio_and_projects() -> None:
    connector = GitlabDeclaredProfileConnector()
    responses = [
        _FakeJsonResponse([{"id": 42, "name": "Alex", "bio": "Platform engineer"}]),
        _FakeJsonResponse(
            [
                {
                    "name": "infra-tools",
                    "description": "Deployment tooling",
                    "star_count": 3,
                    "web_url": "https://gitlab.com/alex-example/infra-tools",
                }
            ]
        ),
    ]

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.gitlab_connector.urlopen",
        side_effect=responses,
    ):
        result = await connector.fetch("https://gitlab.com/alex-example")

    assert result.platform == "gitlab"
    assert "Platform engineer" in result.achievements[0].statement
    assert result.achievements[1].title == "infra-tools"


@pytest.mark.asyncio
async def test_gitlab_connector_raises_when_profile_missing() -> None:
    connector = GitlabDeclaredProfileConnector()
    with (
        patch(
            "rezumi.modules.career_record.infrastructure.declared_profile.gitlab_connector.urlopen",
            return_value=_FakeJsonResponse([]),
        ),
        pytest.raises(DeclaredProfileFetchFailed),
    ):
        await connector.fetch("https://gitlab.com/nobody")


# --- Bitbucket ------------------------------------------------------------


def test_bitbucket_connector_supports_user_urls() -> None:
    connector = BitbucketDeclaredProfileConnector()
    assert connector.supports("https://bitbucket.org/alex-example")
    assert not connector.supports("https://gitlab.com/alex")


@pytest.mark.asyncio
async def test_bitbucket_connector_extracts_repos() -> None:
    connector = BitbucketDeclaredProfileConnector()
    responses = [
        _FakeJsonResponse({"display_name": "Alex Example"}),
        _FakeJsonResponse(
            {
                "values": [
                    {
                        "name": "api-service",
                        "description": "Backend service",
                        "language": "python",
                        "links": {"html": {"href": "https://bitbucket.org/alex/api-service"}},
                    }
                ],
                "next": None,
            }
        ),
    ]

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.bitbucket_connector.urlopen",
        side_effect=responses,
    ):
        result = await connector.fetch("https://bitbucket.org/alex-example")

    assert result.platform == "bitbucket"
    assert result.achievements[1].title == "api-service"
    assert "python" in result.achievements[1].statement.casefold()


# --- Stack Overflow ---------------------------------------------------------


def test_stackoverflow_connector_supports_user_urls() -> None:
    connector = StackExchangeDeclaredProfileConnector()
    assert connector.supports("https://stackoverflow.com/users/12345/alex-example")
    assert not connector.supports("https://stackoverflow.com/questions/1")


@pytest.mark.asyncio
async def test_stackoverflow_connector_includes_attribution() -> None:
    connector = StackExchangeDeclaredProfileConnector()
    payload = {
        "items": [
            {
                "display_name": "Alex Example",
                "reputation": 4321,
                "badge_counts": {"gold": 1, "silver": 5, "bronze": 12},
            }
        ]
    }

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile."
        "stackexchange_connector.urlopen",
        return_value=_FakeJsonResponse(payload),
    ):
        result = await connector.fetch("https://stackoverflow.com/users/12345/alex-example")

    assert result.platform == "stackoverflow"
    assert "4321 reputation" in result.achievements[0].statement
    assert "Powered by Stack Exchange" in result.achievements[0].statement


# --- Codeforces -------------------------------------------------------------


def test_codeforces_connector_supports_profile_urls() -> None:
    connector = CodeforcesDeclaredProfileConnector()
    assert connector.supports("https://codeforces.com/profile/alex_example")
    assert not connector.supports("https://codeforces.com/contest/1")


@pytest.mark.asyncio
async def test_codeforces_connector_buckets_solved_problems_by_tier() -> None:
    connector = CodeforcesDeclaredProfileConnector()
    info_payload = {
        "status": "OK",
        "result": [{"handle": "alex_example", "rating": 1500, "maxRating": 1600, "rank": "expert"}],
    }
    status_payload = {
        "status": "OK",
        "result": [
            {
                "verdict": "OK",
                "problem": {"contestId": 1, "index": "A", "rating": 900},
            },
            {
                "verdict": "OK",
                "problem": {"contestId": 1, "index": "A", "rating": 900},
            },
            {
                "verdict": "WRONG_ANSWER",
                "problem": {"contestId": 1, "index": "B", "rating": 1300},
            },
            {
                "verdict": "OK",
                "problem": {"contestId": 2, "index": "C", "rating": 2000},
            },
        ],
    }

    with (
        patch(
            "rezumi.modules.career_record.infrastructure.declared_profile."
            "codeforces_connector.urlopen",
            side_effect=[
                _FakeJsonResponse(info_payload),
                _FakeJsonResponse(status_payload),
            ],
        ),
        patch(
            "rezumi.modules.career_record.infrastructure.declared_profile."
            "codeforces_connector.time.sleep",
        ),
    ):
        result = await connector.fetch("https://codeforces.com/profile/alex_example")

    statement = result.achievements[0].statement
    assert "Rating 1500" in statement
    # Deduplicated by problem (contestId/index) — the repeated 1-A submission
    # counts once, and the failed 1-B submission never counts.
    assert "Easy (1)" in statement
    assert "Hard (1)" in statement
    assert "Medium" not in statement


# --- dev.to ------------------------------------------------------------


def test_devto_connector_supports_user_urls() -> None:
    connector = DevToDeclaredProfileConnector()
    assert connector.supports("https://dev.to/alex-example")
    # An article link still identifies the author whose activity is read.
    assert connector.supports("https://dev.to/alex-example/some-post-slug")
    assert not connector.supports("https://dev.to/t/python")
    assert not connector.supports("https://dev.to/")


@pytest.mark.asyncio
async def test_devto_connector_extracts_summary_and_reactions() -> None:
    connector = DevToDeclaredProfileConnector()
    user_payload = {"id": 1, "name": "Alex Example", "summary": "Writes about backend systems."}
    articles_payload = [
        {"positive_reactions_count": 10},
        {"positive_reactions_count": 5},
    ]

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.devto_connector.urlopen",
        side_effect=[_FakeJsonResponse(user_payload), _FakeJsonResponse(articles_payload)],
    ):
        result = await connector.fetch("https://dev.to/alex-example")

    assert result.platform == "devto"
    assert "backend systems" in result.achievements[0].statement
    assert "15 total reactions" in result.achievements[0].statement


# --- ORCID (built but disabled by default) ----------------------------------


def test_orcid_connector_supports_orcid_id_urls() -> None:
    connector = OrcidDeclaredProfileConnector()
    assert connector.supports("https://orcid.org/0000-0002-1825-0097")
    assert not connector.supports("https://orcid.org/not-an-id")


@pytest.mark.asyncio
async def test_orcid_connector_extracts_works() -> None:
    connector = OrcidDeclaredProfileConnector()
    payload = {
        "group": [
            {
                "work-summary": [
                    {
                        "title": {"title": {"value": "Distributed consensus at scale"}},
                        "journal-title": {"value": "Journal of Systems"},
                        "publication-date": {"year": {"value": "2025"}},
                        "url": None,
                    }
                ]
            }
        ]
    }

    with patch(
        "rezumi.modules.career_record.infrastructure.declared_profile.orcid_connector.urlopen",
        return_value=_FakeJsonResponse(payload),
    ):
        result = await connector.fetch("https://orcid.org/0000-0002-1825-0097")

    assert result.platform == "orcid"
    assert result.achievements[0].title == "Distributed consensus at scale"
    assert "Journal of Systems" in result.achievements[0].statement


def test_orcid_connector_is_disabled_by_default_in_registry() -> None:
    """ORCID stays off, but the link still reads - from OpenAlex, under CC0."""

    registry = default_declared_profile_registry()
    assert registry.resolve("https://orcid.org/0000-0002-1825-0097").platform == "openalex"


def test_orcid_connector_is_available_when_explicitly_enabled() -> None:
    registry = default_declared_profile_registry(orcid_enabled=True)
    connector = registry.resolve("https://orcid.org/0000-0002-1825-0097")
    assert connector.platform == "orcid"


# --- Registry / portfolio fallback exclusions -------------------------------


def test_portfolio_connector_defers_to_known_api_platform_hosts() -> None:
    connector = PortfolioDeclaredProfileConnector()
    for host in (
        "gitlab.com",
        "bitbucket.org",
        "stackoverflow.com",
        "codeforces.com",
        "dev.to",
        "orcid.org",
    ):
        assert not connector.supports(f"https://{host}/someone")


def test_default_registry_resolves_every_new_platform() -> None:
    registry = default_declared_profile_registry()
    assert registry.resolve("https://gitlab.com/alex").platform == "gitlab"
    assert registry.resolve("https://bitbucket.org/alex").platform == "bitbucket"
    assert registry.resolve("https://stackoverflow.com/users/1/alex").platform == "stackexchange"
    assert (
        registry.resolve("https://quant.stackexchange.com/users/1/alex").platform == "stackexchange"
    )
    assert registry.resolve("https://codeforces.com/profile/alex").platform == "codeforces"
    assert registry.resolve("https://dev.to/alex").platform == "devto"
