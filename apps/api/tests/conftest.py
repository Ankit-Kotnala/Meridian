"""API test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app


class FakeDatabase:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.disposed = False
        self.ping_count = 0

    async def ping(self) -> None:
        self.ping_count += 1
        if self.failure is not None:
            raise self.failure

    async def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {
            "environment": "test",
            "log_format": "json",
            "trusted_hosts": ["testserver"],
        }
    )


@pytest.fixture
def fake_database() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def client(settings: Settings, fake_database: FakeDatabase) -> Iterator[TestClient]:
    with TestClient(create_app(settings, database=fake_database)) as test_client:
        yield test_client
