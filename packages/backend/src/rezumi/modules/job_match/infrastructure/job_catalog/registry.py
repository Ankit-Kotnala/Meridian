"""Default set of always-on, zero-config catalog connectors."""

from __future__ import annotations

from rezumi.modules.job_match.application.job_catalog_ports import JobCatalogSourceConnector
from rezumi.modules.job_match.infrastructure.job_catalog.arbeitnow_connector import (
    ArbeitnowCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.remoteok_connector import (
    RemoteOkCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.remotive_connector import (
    RemotiveCatalogConnector,
)


def default_job_catalog_connectors() -> tuple[JobCatalogSourceConnector, ...]:
    """Multi-employer, no-auth published feeds — no per-company config needed."""
    return (
        RemotiveCatalogConnector(),
        RemoteOkCatalogConnector(),
        ArbeitnowCatalogConnector(),
    )
