"""Celery delivery adapter for the shared job catalog sync pipeline."""

import asyncio

import structlog

from rezumi_worker.app import celery_app
from rezumi_worker.config import get_settings
from rezumi_worker.runtime import sync_job_catalog
from rezumi_worker.task_names import SYNC_JOB_CATALOG_TASK
from rezumi_worker.tasks.contracts import JobCatalogSyncTaskResult

logger = structlog.get_logger(__name__)


@celery_app.task(name=SYNC_JOB_CATALOG_TASK)  # type: ignore[untyped-decorator]
def sync_job_catalog_task() -> JobCatalogSyncTaskResult:
    """Enumerate every configured published job feed into the shared catalog.

    Runs on a long interval (see WorkerSettings.job_catalog_sync_interval_seconds,
    default 6h) to respect the free-tier request limits published by these
    sources. One source failing does not block the others; failures are
    logged with counts only, never listing content.
    """
    results = asyncio.run(sync_job_catalog(get_settings()))
    for result in results:
        if result.rejected:
            logger.warning(
                "job_catalog_source_rejected_listings",
                platform=result.platform,
                fetched=result.fetched,
                upserted=result.upserted,
                rejected=result.rejected,
            )
        else:
            logger.info(
                "job_catalog_source_synced",
                platform=result.platform,
                fetched=result.fetched,
                upserted=result.upserted,
            )
    return {
        "sources": [
            {
                "platform": result.platform,
                "fetched": result.fetched,
                "upserted": result.upserted,
                "rejected": result.rejected,
            }
            for result in results
        ]
    }
