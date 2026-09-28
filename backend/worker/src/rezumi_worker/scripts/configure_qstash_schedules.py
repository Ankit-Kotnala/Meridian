"""Idempotently install the two low-volume cloud schedules.

Run this once after the public job-runner service has a stable HTTPS URL, and
again after changing the runner hostname.  The custom schedule IDs mean reruns
replace the existing schedules instead of duplicating them.
"""

from __future__ import annotations

import asyncio

from rezumi.integrations.jobs import QStashClient, QStashOptions

from rezumi_worker.config import get_settings

_MAINTENANCE_SCHEDULE_ID = "rezumi-maintenance-v1"
_CATALOG_SCHEDULE_ID = "rezumi-job-catalog-v1"
_MAINTENANCE_TASK = "rezumi.cloud.maintenance.sweep"
_CATALOG_TASK = "rezumi.worker.job_match.sync_job_catalog"


async def configure() -> None:
    settings = get_settings()
    if settings.job_delivery_provider != "qstash":
        raise RuntimeError("JOB_DELIVERY_PROVIDER must be qstash to configure cloud schedules")
    token = settings.qstash_token
    destination = settings.qstash_job_runner_url
    if token is None or destination is None:
        raise RuntimeError("validated QStash configuration is unavailable")
    client = QStashClient(
        QStashOptions(
            token=token.get_secret_value(),
            destination_url=destination,
            base_url=settings.qstash_base_url,
            retries=settings.qstash_retries,
            delivery_timeout_seconds=settings.qstash_delivery_timeout_seconds,
        )
    )
    await client.upsert_schedule(
        schedule_id=_MAINTENANCE_SCHEDULE_ID,
        cron="*/15 * * * *",
        payload={"task": _MAINTENANCE_TASK, "limit": 25},
    )
    await client.upsert_schedule(
        schedule_id=_CATALOG_SCHEDULE_ID,
        cron="17 3 * * *",
        payload={"task": _CATALOG_TASK},
    )
    print("Configured QStash schedules: maintenance (15 min), job catalog (daily UTC).")


if __name__ == "__main__":
    asyncio.run(configure())
