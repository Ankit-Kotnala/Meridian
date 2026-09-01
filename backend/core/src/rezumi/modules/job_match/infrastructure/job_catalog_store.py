"""MongoDB adapter for the shared job catalog."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, TEXT, MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from rezumi.foundation.config.mongodb import MongoOptions
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
        self, *, keywords: tuple[str, ...], limit: int, offset: int = 0
    ) -> tuple[CatalogJobListing, ...]:
        del keywords, limit, offset
        return ()

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
        collection.create_index(
            [("title", TEXT), ("company", TEXT), ("sourceText", TEXT)],
            name="job_catalog_text_search",
        )

    async def ping(self) -> None:
        await self._run(self._client.admin.command, "ping")

    async def upsert_listing(self, listing: CatalogJobListing, *, fetched_at: datetime) -> None:
        document = {
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
        await self._run(
            self._collection.update_one,
            {"platform": listing.platform, "externalId": listing.external_id},
            {
                "$set": document,
                "$setOnInsert": {"createdAt": fetched_at},
            },
            upsert=True,
        )

    async def search(
        self, *, keywords: tuple[str, ...], limit: int, offset: int = 0
    ) -> tuple[CatalogJobListing, ...]:
        bounded_limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
        bounded_offset = max(0, offset)
        if not keywords:
            cursor = (
                self._collection.find({})
                .sort("fetchedAt", -1)
                .skip(bounded_offset)
                .limit(bounded_limit)
            )
            documents = await self._run(list, cursor)
        else:
            search_text = " ".join(keyword.strip() for keyword in keywords if keyword.strip())
            if not search_text:
                return ()
            cursor = (
                self._collection.find({"$text": {"$search": search_text}})
                .sort([("score", {"$meta": "textScore"})])
                .skip(bounded_offset)
                .limit(bounded_limit)
            )
            documents = await self._run(list, cursor)
        return tuple(_listing(document) for document in documents)

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
