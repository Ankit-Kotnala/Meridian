"""MongoDB adapter for owner-scoped Application Profile documents."""

from __future__ import annotations

import asyncio
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from rezumi.foundation.config.mongodb import MongoOptions
from rezumi.modules.application_workspace.domain import (
    ApplicationProfile,
    ApplicationWorkspaceUnavailable,
)


class DisabledApplicationProfileDocumentStore:
    """No-op adapter used when MongoDB storage is disabled."""

    async def upsert(self, profile: ApplicationProfile) -> None:
        del profile
        return None

    async def ping(self) -> None:
        return None

    async def dispose(self) -> None:
        return None


class MongoApplicationProfileDocumentStore:
    """Persist Application Profile payloads keyed by ``ownerUserId``."""

    def __init__(self, options: MongoOptions) -> None:
        self._options = options
        self._client: MongoClient[Any] = MongoClient(
            options.url,
            connectTimeoutMS=options.connect_timeout_ms,
            serverSelectionTimeoutMS=options.server_selection_timeout_ms,
        )
        self._collection = self._client[options.database_name][options.collection_name]
        self._ensure_indexes(self._collection)

    @staticmethod
    def _ensure_indexes(collection: Collection[Any]) -> None:
        collection.create_index("ownerUserId", unique=True)

    async def ping(self) -> None:
        await self._run(self._client.admin.command, "ping")

    async def upsert(self, profile: ApplicationProfile) -> None:
        document = _document(profile)
        await self._run(
            self._collection.update_one,
            {"ownerUserId": document["ownerUserId"]},
            {
                "$set": document,
                "$setOnInsert": {"createdAt": document["updatedAt"]},
            },
            upsert=True,
        )

    async def dispose(self) -> None:
        await self._run(self._client.close)

    async def _run(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except PyMongoError as exc:
            raise ApplicationWorkspaceUnavailable from exc


def _document(profile: ApplicationProfile) -> dict[str, Any]:
    return {
        "ownerUserId": str(profile.owner_user_id),
        "profileId": str(profile.id),
        "workAuthorization": profile.work_authorization,
        "noticePeriodDays": profile.notice_period_days,
        "compensationMin": profile.compensation_min,
        "compensationMax": profile.compensation_max,
        "compensationCurrency": profile.compensation_currency,
        "preferredLocations": list(profile.preferred_locations),
        "profileLinks": [{"label": link.label, "url": link.url} for link in profile.profile_links],
        "voluntaryDisclosures": dict(profile.voluntary_disclosures),
        "version": profile.version,
        "updatedAt": profile.updated_at.isoformat(),
    }
