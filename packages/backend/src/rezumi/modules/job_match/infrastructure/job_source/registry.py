"""Registry of configured job-source connectors."""

from __future__ import annotations

from collections.abc import Sequence

from rezumi.modules.job_match.application.job_source_ports import JobSourceConnector
from rezumi.modules.job_match.domain import JobMatchValidationError

from .fake_connector import FakeJobSourceConnector
from .greenhouse_connector import GreenhouseJobSourceConnector


def default_job_source_registry() -> tuple[JobSourceConnector, ...]:
    return (
        FakeJobSourceConnector(),
        GreenhouseJobSourceConnector(),
    )


class DefaultJobSourceConnectorRegistry:
    def __init__(self, connectors: Sequence[JobSourceConnector]) -> None:
        self._connectors = {connector.platform: connector for connector in connectors}
        if len(self._connectors) != len(connectors):
            raise ValueError("job source connector platforms must be unique")

    def resolve(self, platform: str) -> JobSourceConnector:
        normalized = platform.strip().casefold()
        connector = self._connectors.get(normalized)
        if connector is None:
            raise JobMatchValidationError("job source platform is not supported")
        return connector
