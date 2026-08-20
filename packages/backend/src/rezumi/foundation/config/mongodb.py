"""MongoDB connection options for optional parsed-resume document storage."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ


@dataclass(frozen=True, slots=True)
class MongoOptions:
    url: str
    database_name: str = "Rezumi"
    collection_name: str = "user-data"
    connect_timeout_ms: int = 3_000
    server_selection_timeout_ms: int = 3_000


def mongodb_url_from_environment() -> str:
    return environ.get("MONGODB_URL", "mongodb://localhost:27017")
