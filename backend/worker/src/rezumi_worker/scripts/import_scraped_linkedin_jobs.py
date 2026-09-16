"""Import scraped LinkedIn job JSON into the shared MongoDB job catalog.

    uv run --project backend python -m rezumi_worker.scripts.import_scraped_linkedin_jobs \\
        --file /path/to/scraped_jobs_data.json

Uses idempotent upserts keyed by (platform=linkedin, externalId=job_id).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from rezumi.foundation.config.mongodb import MongoOptions
from rezumi.modules.job_match.infrastructure.job_catalog.linkedin_scraped import (
    PLATFORM,
    listing_from_scraped_record,
    load_scraped_jobs,
)
from rezumi.modules.job_match.infrastructure.job_catalog_store import MongoJobCatalogStore

from rezumi_worker.config import get_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="Path to scraped_jobs_data JSON export",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Bulk upsert batch size (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate only; do not write to MongoDB",
    )
    return parser.parse_args()


async def _import_file(path: Path, *, batch_size: int, dry_run: bool) -> int:
    records = load_scraped_jobs(path)
    print(f"Loaded {len(records)} scraped records from {path}")

    mapped = []
    rejected = 0
    for record in records:
        listing = listing_from_scraped_record(record)
        if listing is None:
            rejected += 1
            continue
        mapped.append(listing)

    print(
        f"Mapped {len(mapped)} {PLATFORM} listings ({rejected} rejected as incomplete or invalid)."
    )
    if dry_run:
        print("Dry run complete — no database writes performed.")
        return 0

    settings = get_settings()
    if not settings.mongodb_enabled:
        print("MongoDB is disabled in settings; enable it before importing.", file=sys.stderr)
        return 1

    store = MongoJobCatalogStore(
        MongoOptions(
            url=settings.mongodb_url,
            database_name=settings.mongodb_database,
            collection_name=settings.mongodb_job_catalog_collection,
        )
    )
    try:
        await store.ping()
        now = datetime.now(tz=UTC)
        upserted = 0
        batch_size = max(1, batch_size)
        for start in range(0, len(mapped), batch_size):
            batch = tuple(mapped[start : start + batch_size])
            upserted += await store.bulk_upsert_listings(batch, fetched_at=now)
            print(f"Upserted {upserted}/{len(mapped)} listings…")
    finally:
        await store.dispose()

    print(f"Import complete: {upserted} {PLATFORM} listings upserted.")
    return 0


def main() -> int:
    args = _parse_args()
    if not args.file.is_file():
        print(f"File not found: {args.file}", file=sys.stderr)
        return 1
    return asyncio.run(_import_file(args.file, batch_size=args.batch_size, dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
