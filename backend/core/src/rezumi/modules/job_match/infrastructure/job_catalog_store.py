"""MongoDB adapter for the shared job catalog."""

from __future__ import annotations

import asyncio
import contextlib
import re
from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, TEXT, MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from rezumi.foundation.config.mongodb import MongoOptions
from rezumi.modules.job_match.application.job_catalog_filters import normalized_terms, term_regex
from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
from rezumi.modules.job_match.domain.errors import JobMatchUnavailable

_MAX_SEARCH_LIMIT = 200


class DisabledJobCatalogStore:
    """No-op adapter used when MongoDB storage is disabled."""

    async def ping(self) -> None:
        return None

    async def upsert_listing(self, listing: CatalogJobListing, *, fetched_at: datetime) -> None:
        del listing, fetched_at
        return None

    async def search(
        self,
        *,
        keywords: tuple[str, ...],
        limit: int,
        offset: int = 0,
        platform: str | None = None,
        location: str | None = None,
        seniority: str | None = None,
        work_model: str | None = None,
    ) -> tuple[CatalogJobListing, ...]:
        del keywords, limit, offset, platform, location, seniority, work_model
        return ()

    async def count(
        self,
        *,
        keywords: tuple[str, ...],
        platform: str | None = None,
        location: str | None = None,
        seniority: str | None = None,
        work_model: str | None = None,
    ) -> int:
        del keywords, platform, location, seniority, work_model
        return 0

    async def get_listing(self, platform: str, external_id: str) -> CatalogJobListing | None:
        del platform, external_id
        return None

    async def dispose(self) -> None:
        return None


class MongoJobCatalogStore:
    """Persist shared job-catalog listings keyed by (platform, externalId)."""

    def __init__(self, options: MongoOptions) -> None:
        self._client: MongoClient[Any] = MongoClient(
            options.url,
            connectTimeoutMS=options.connect_timeout_ms,
            serverSelectionTimeoutMS=options.server_selection_timeout_ms,
        )
        self._collection = self._client[options.database_name][options.collection_name]
        self._ensure_indexes(self._collection)

    @staticmethod
    def _ensure_indexes(collection: Collection[Any]) -> None:
        collection.create_index([("platform", ASCENDING), ("externalId", ASCENDING)], unique=True)
        collection.create_index([("platform", ASCENDING), ("postedAt", ASCENDING)])
        with contextlib.suppress(PyMongoError):
            collection.drop_index("job_catalog_text_search")
        collection.create_index(
            [("title", TEXT), ("company", TEXT), ("location", TEXT), ("sourceText", TEXT)],
            name="job_catalog_text_search",
        )

    async def ping(self) -> None:
        await self._run(self._client.admin.command, "ping")

    async def upsert_listing(self, listing: CatalogJobListing, *, fetched_at: datetime) -> None:
        await self._run(
            self._collection.update_one,
            {"platform": listing.platform, "externalId": listing.external_id},
            {
                "$set": _listing_document(listing, fetched_at=fetched_at),
                "$setOnInsert": {"createdAt": fetched_at},
            },
            upsert=True,
        )

    async def bulk_upsert_listings(
        self,
        listings: tuple[CatalogJobListing, ...],
        *,
        fetched_at: datetime,
    ) -> int:
        if not listings:
            return 0
        operations = [
            UpdateOne(
                {"platform": listing.platform, "externalId": listing.external_id},
                {
                    "$set": _listing_document(listing, fetched_at=fetched_at),
                    "$setOnInsert": {"createdAt": fetched_at},
                },
                upsert=True,
            )
            for listing in listings
        ]
        result = await self._run(
            self._collection.bulk_write,
            operations,
            ordered=False,
        )
        return int(result.upserted_count + result.modified_count)

    async def search(
        self,
        *,
        keywords: tuple[str, ...],
        limit: int,
        offset: int = 0,
        platform: str | None = None,
        location: str | None = None,
        seniority: str | None = None,
        work_model: str | None = None,
    ) -> tuple[CatalogJobListing, ...]:
        bounded_limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
        bounded_offset = max(0, offset)
        filter_document = _search_filter(
            keywords,
            platform=platform,
            location=location,
            seniority=seniority,
            work_model=work_model,
        )
        if filter_document is None:
            return ()
        cursor = (
            self._collection.find(filter_document)
            .sort([("postedAt", -1), ("fetchedAt", -1)])
            .skip(bounded_offset)
            .limit(bounded_limit)
        )
        documents = await self._run(list, cursor)
        return tuple(_listing(document) for document in documents)

    async def count(
        self,
        *,
        keywords: tuple[str, ...],
        platform: str | None = None,
        location: str | None = None,
        seniority: str | None = None,
        work_model: str | None = None,
    ) -> int:
        filter_document = _search_filter(
            keywords,
            platform=platform,
            location=location,
            seniority=seniority,
            work_model=work_model,
        )
        if filter_document is None:
            return 0
        counted = await self._run(self._collection.count_documents, filter_document)
        return int(counted)

    async def get_listing(self, platform: str, external_id: str) -> CatalogJobListing | None:
        document = await self._run(
            self._collection.find_one, {"platform": platform, "externalId": external_id}
        )
        return _listing(document) if document is not None else None

    async def dispose(self) -> None:
        await self._run(self._client.close)

    async def _run(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except PyMongoError as exc:
            raise JobMatchUnavailable from exc


def _listing_document(listing: CatalogJobListing, *, fetched_at: datetime) -> dict[str, Any]:
    return {
        "platform": listing.platform,
        "externalId": listing.external_id,
        "title": listing.title,
        "company": listing.company,
        "location": listing.location,
        "remote": listing.remote,
        "applicationUrl": listing.application_url,
        "sourceText": listing.source_text,
        "postedAt": listing.posted_at,
        "fetchedAt": fetched_at,
    }


_SENIORITY_REGEX = {
    "internship": r"\b(intern|internship|trainee|apprentice)\b",
    "principal": r"\b(principal|distinguished|fellow|director|head of|vp)\b",
    "staff": r"\b(staff|architect)\b",
    "senior": r"\b(senior|sr\.?|lead)\b",
    "junior": r"\b(junior|jr\.?|graduate|entry[- ]level|associate)\b",
}
_REMOTE_REGEX = r"\b(remote|anywhere|worldwide|work from home)\b"
_HYBRID_REGEX = r"\bhybrid\b"


def _contains_term(term: str) -> dict[str, Any]:
    pattern = term_regex(term)
    return {
        "$or": [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"company": {"$regex": pattern, "$options": "i"}},
        ]
    }


def _seniority_clause(seniority: str) -> dict[str, Any] | None:
    if seniority == "mid":
        return {
            "$nor": [
                {"title": {"$regex": pattern, "$options": "i"}}
                for pattern in _SENIORITY_REGEX.values()
            ]
        }
    pattern = _SENIORITY_REGEX.get(seniority)
    if not pattern:
        return None
    return {"title": {"$regex": pattern, "$options": "i"}}


def _work_model_clause(work_model: str) -> dict[str, Any] | None:
    remote = {
        "$or": [
            {"remote": True},
            {"title": {"$regex": _REMOTE_REGEX, "$options": "i"}},
            {"location": {"$regex": _REMOTE_REGEX, "$options": "i"}},
        ]
    }
    hybrid = {
        "$or": [
            {"title": {"$regex": _HYBRID_REGEX, "$options": "i"}},
            {"location": {"$regex": _HYBRID_REGEX, "$options": "i"}},
        ]
    }
    if work_model == "remote":
        return remote
    if work_model == "hybrid":
        return hybrid
    if work_model == "onsite":
        return {"$nor": [remote, hybrid]}
    return None


def _search_filter(
    keywords: tuple[str, ...],
    *,
    platform: str | None = None,
    location: str | None = None,
    seniority: str | None = None,
    work_model: str | None = None,
) -> dict[str, Any] | None:
    """AND-match browse filters on short indexed fields only.

    Keyword search is title/company, not the job-body preview: scanning
    ``sourceText`` across tens of thousands of listings times out, and short
    tokens such as "AI" otherwise match inside words like "training".
    """
    clauses: list[dict[str, Any]] = []
    if platform:
        clauses.append({"platform": platform.strip()})
    location_needle = (location or "").strip()
    if location_needle:
        clauses.append({"location": {"$regex": re.escape(location_needle[:120]), "$options": "i"}})
    seniority_clause = _seniority_clause((seniority or "").strip())
    if seniority_clause is not None:
        clauses.append(seniority_clause)
    work_model_clause = _work_model_clause((work_model or "").strip())
    if work_model_clause is not None:
        clauses.append(work_model_clause)
    for term in normalized_terms(keywords):
        clauses.append(_contains_term(term))
    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _listing(document: dict[str, Any]) -> CatalogJobListing:
    posted_at = document.get("postedAt")
    if isinstance(posted_at, datetime) and posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    return CatalogJobListing(
        platform=document["platform"],
        external_id=document["externalId"],
        title=document["title"],
        company=document.get("company"),
        location=document.get("location"),
        remote=document.get("remote"),
        application_url=document.get("applicationUrl"),
        source_text=document.get("sourceText", ""),
        posted_at=posted_at,
    )
