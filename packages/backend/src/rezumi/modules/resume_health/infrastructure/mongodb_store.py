"""MongoDB adapter for organized parsed-resume documents."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from rezumi.foundation.config.mongodb import MongoOptions
from rezumi.modules.resume_health.domain.errors import RetryableProcessingFailure


class DisabledParsedResumeDocumentStore:
    """No-op adapter used when MongoDB storage is disabled."""

    async def ping(self) -> None:
        return None

    async def upsert(self, document: dict[str, Any]) -> None:
        del document
        return None

    async def delete(self, resume_id: UUID) -> None:
        del resume_id
        return None

    async def dispose(self) -> None:
        return None


class MongoParsedResumeDocumentStore:
    """Persist organized parsed-resume payloads keyed by ``resumeId``."""

    def __init__(self, options: MongoOptions) -> None:
        self._options = options
        self._client = MongoClient(
            options.url,
            connectTimeoutMS=options.connect_timeout_ms,
            serverSelectionTimeoutMS=options.server_selection_timeout_ms,
        )
        self._collection = self._client[options.database_name][options.collection_name]
        self._ensure_indexes(self._collection)

    @staticmethod
    def _ensure_indexes(collection: Collection[Any]) -> None:
        collection.create_index("resumeId", unique=True)
        collection.create_index("userId")
        collection.create_index("guestSessionId")

    async def ping(self) -> None:
        await self._run(self._client.admin.command, "ping")

    async def upsert(self, document: dict[str, Any]) -> None:
        resume_id = document["resumeId"]
        now = document.get("updatedAt")
        await self._run(
            self._collection.update_one,
            {"resumeId": resume_id},
            {
                "$set": document,
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )

    async def delete(self, resume_id: UUID) -> None:
        await self._run(self._collection.delete_one, {"resumeId": str(resume_id)})

    async def dispose(self) -> None:
        await self._run(self._client.close)

    async def _run(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except PyMongoError as exc:
            raise RetryableProcessingFailure("parsed_resume_store_unavailable") from exc
