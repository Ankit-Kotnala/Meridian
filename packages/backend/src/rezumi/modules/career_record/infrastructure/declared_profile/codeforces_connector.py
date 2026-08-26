"""Codeforces public profile connector using the documented public API.

Surfaces solved-problem counts bucketed by difficulty tier rather than one
raw total — a candidate who solved 50 easy problems and one who solved 20
spanning easy/medium/hard both get an honest, distinct signal instead of a
single number that would just reward volume (see docs/scoring-methodology.md
anti-bias notes).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileAchievement,
    DeclaredProfileFetchFailed,
    DeclaredProfileFetchResult,
    hostname,
    normalize_declared_profile_url,
)

_CODEFORCES_HANDLE = re.compile(r"^profile/(?P<handle>[A-Za-z0-9_.-]{1,64})/?$")
_TIMEOUT = 8.0
_MAX_SUBMISSIONS = 1_000
_TIERS: tuple[tuple[str, int, int], ...] = (
    ("Easy", 0, 1199),
    ("Medium", 1200, 1899),
    ("Hard", 1900, 10_000),
)


class CodeforcesDeclaredProfileConnector:
    """Reads a user's public Codeforces rating and solved-problem tiers."""

    platform = "codeforces"

    def supports(self, url: str) -> bool:
        normalized = normalize_declared_profile_url(url)
        if hostname(normalized) != "codeforces.com":
            return False
        path = urlsplit(normalized).path.strip("/")
        return _CODEFORCES_HANDLE.match(f"{path}/") is not None

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        normalized = normalize_declared_profile_url(url)
        path = urlsplit(normalized).path.strip("/")
        match = _CODEFORCES_HANDLE.match(f"{path}/")
        if match is None:
            raise DeclaredProfileFetchFailed("Codeforces profile URL is not supported")
        handle = match.group("handle")
        return await asyncio.to_thread(self._fetch_sync, normalized, handle)

    def _fetch_sync(self, profile_url: str, handle: str) -> DeclaredProfileFetchResult:
        info = self._get_json(f"https://codeforces.com/api/user.info?handles={handle}")
        info_result = info.get("result") if isinstance(info, dict) else None
        if not isinstance(info_result, list) or not info_result:
            raise DeclaredProfileFetchFailed("Codeforces profile was not found")
        user = info_result[0] if isinstance(info_result[0], dict) else {}

        rating = user.get("rating")
        max_rating = user.get("maxRating")
        rank = str(user.get("rank") or "").strip()

        # Codeforces enforces a hard 1-request-per-2-seconds limit per source;
        # this is the second of two calls this fetch makes.
        time.sleep(2)
        status = self._get_json(
            f"https://codeforces.com/api/user.status?handle={handle}"
            f"&from=1&count={_MAX_SUBMISSIONS}"
        )
        submissions = status.get("result") if isinstance(status, dict) else None
        tier_counts = self._solved_by_tier(submissions if isinstance(submissions, list) else [])

        parts: list[str] = []
        if isinstance(rating, int):
            parts.append(f"Rating {rating}" + (f" (max {max_rating})." if max_rating else "."))
        if rank:
            parts.append(f"Rank: {rank}.")
        tier_text = ", ".join(
            f"{label} ({count})" for label, count in tier_counts.items() if count > 0
        )
        if tier_text:
            suffix = "+" if len(submissions or []) >= _MAX_SUBMISSIONS else ""
            parts.append(f"Solved problems by difficulty tier: {tier_text}{suffix}.")

        if not parts:
            raise DeclaredProfileFetchFailed(
                "Codeforces profile did not expose public achievements"
            )
        statement = " ".join(parts)

        return DeclaredProfileFetchResult(
            platform=self.platform,
            profile_url=profile_url,
            fetched_at=datetime.now(tz=UTC),
            achievements=(
                DeclaredProfileAchievement(
                    title=f"{handle} on Codeforces",
                    statement=statement,
                    source_url=profile_url,
                    excerpt=statement[:500],
                ),
            ),
        )

    def _solved_by_tier(self, submissions: list[Any]) -> dict[str, int]:
        solved: set[str] = set()
        tier_counts = {label: 0 for label, _, _ in _TIERS}
        for submission in submissions:
            if not isinstance(submission, dict) or submission.get("verdict") != "OK":
                continue
            problem = submission.get("problem")
            if not isinstance(problem, dict):
                continue
            key = f"{problem.get('contestId')}-{problem.get('index')}"
            if key in solved:
                continue
            solved.add(key)
            problem_rating = problem.get("rating")
            if not isinstance(problem_rating, int):
                continue
            for label, low, high in _TIERS:
                if low <= problem_rating <= high:
                    tier_counts[label] += 1
                    break
        return tier_counts

    def _get_json(self, url: str) -> Any:
        request = Request(  # noqa: S310 - fixed Codeforces API host
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RezumiDeclaredProfile/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
                payload = response.read(2_000_000)
        except HTTPError as exc:
            if exc.code == 404:
                raise DeclaredProfileFetchFailed("Codeforces profile was not found") from exc
            raise DeclaredProfileFetchFailed("Codeforces profile could not be read") from exc
        except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
            raise DeclaredProfileFetchFailed("Codeforces profile could not be read") from exc
        decoded = json.loads(payload.decode("utf-8"))
        if isinstance(decoded, dict) and decoded.get("status") == "FAILED":
            raise DeclaredProfileFetchFailed(
                str(decoded.get("comment") or "Codeforces profile could not be read")
            )
        return decoded
