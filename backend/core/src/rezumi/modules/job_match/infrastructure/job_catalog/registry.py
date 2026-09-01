"""Default set of always-on, zero-config catalog connectors."""

from __future__ import annotations

from rezumi.modules.job_match.application.job_catalog_ports import JobCatalogSourceConnector
from rezumi.modules.job_match.infrastructure.job_catalog.arbeitnow_connector import (
    ArbeitnowCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.ashby_connector import (
    AshbyIndiaCatalogConnector,
    AshbyIndiaCatalogOptions,
)
from rezumi.modules.job_match.infrastructure.job_catalog.greenhouse_connector import (
    GreenhouseIndiaCatalogConnector,
    GreenhouseIndiaCatalogOptions,
)
from rezumi.modules.job_match.infrastructure.job_catalog.himalayas_connector import (
    HimalayasCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.jobicy_connector import (
    JobicyCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.remoteok_connector import (
    RemoteOkCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.remotive_connector import (
    RemotiveCatalogConnector,
)


def default_job_catalog_connectors(
    *,
    greenhouse_india_options: GreenhouseIndiaCatalogOptions | None = None,
    greenhouse_global_options: GreenhouseIndiaCatalogOptions | None = None,
    ashby_india_options: AshbyIndiaCatalogOptions | None = None,
) -> tuple[JobCatalogSourceConnector, ...]:
    """Published feeds and explicitly configured public India employer boards."""
    connectors: tuple[JobCatalogSourceConnector, ...] = (
        RemotiveCatalogConnector(),
        RemoteOkCatalogConnector(),
        ArbeitnowCatalogConnector(),
        HimalayasCatalogConnector(),
        JobicyCatalogConnector(),
    )
    if greenhouse_india_options is not None:
        connectors += (GreenhouseIndiaCatalogConnector(greenhouse_india_options),)
    if greenhouse_global_options is not None:
        connectors += (GreenhouseIndiaCatalogConnector(greenhouse_global_options),)
    if ashby_india_options is not None:
        connectors += (AshbyIndiaCatalogConnector(ashby_india_options),)
    return connectors
