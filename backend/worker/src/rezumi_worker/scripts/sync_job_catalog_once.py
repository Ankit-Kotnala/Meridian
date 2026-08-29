"""Run the job-catalog sync pipeline once, synchronously, outside Celery.

    uv run --project backend python -m rezumi_worker.scripts.sync_job_catalog_once

Uses the exact same code path as the scheduled Celery task
(`rezumi_worker.tasks.job_match.sync_job_catalog_task`) — only the trigger
differs.
"""

from __future__ import annotations

import asyncio
import sys

from rezumi_worker.config import get_settings
from rezumi_worker.runtime import sync_job_catalog


def main() -> int:
    results = asyncio.run(sync_job_catalog(get_settings()))
    if not results:
        print("No job catalog sources configured.")
        return 1
    total_upserted = 0
    for result in results:
        print(
            f"{result.platform}: fetched={result.fetched} "
            f"upserted={result.upserted} rejected={result.rejected}"
        )
        total_upserted += result.upserted
    print(f"Total upserted: {total_upserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
