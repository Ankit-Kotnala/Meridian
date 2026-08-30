"use client";

import { Bookmark, BookmarkCheck, ExternalLink } from "lucide-react";

import { Badge, Card, EmptyState, cn } from "@rezumi/ui";

import type { JobCatalogListing } from "../api/types";

import { listingKey } from "./job-selection";

/** Middle column of the job search: the result list itself. */
export function JobListingResults({
  description,
  listings,
  onOpen,
  onSave,
  savedKeys,
  savingKey,
  selectedKey,
  totalCount,
}: {
  description: string;
  listings: readonly JobCatalogListing[];
  onOpen: (listing: JobCatalogListing) => void;
  onSave: (listing: JobCatalogListing) => void;
  savedKeys: ReadonlySet<string>;
  savingKey: string | undefined;
  selectedKey: string | undefined;
  totalCount: number;
}) {
  return (
    <Card as="section" aria-labelledby="job-results-heading">
      <div className="px-5 pb-4 pt-5">
        <h2
          className="text-base font-semibold tracking-[-0.01em] text-foreground"
          id="job-results-heading"
        >
          Suggested for you
        </h2>
        <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
      </div>

      {listings.length === 0 ? (
        <div className="px-5 pb-5">
          <EmptyState
            description="No listings matched these filters. Clear them to see every suggestion again."
            title="No results"
          />
        </div>
      ) : (
        <ul className="border-t border-line">
          {listings.map((listing) => {
            const key = listingKey(listing);
            const selected = key === selectedKey;
            const saved = savedKeys.has(key);
            return (
              <li
                className={cn(
                  "border-b border-line border-l-[3px] transition-colors last:border-b-0",
                  selected
                    ? "border-l-primary bg-primary-soft"
                    : "border-l-transparent hover:bg-surface-subtle/60",
                )}
                key={key}
              >
                <button
                  aria-current={selected ? "true" : undefined}
                  className="block w-full px-4 py-3.5 text-left"
                  onClick={() => onOpen(listing)}
                  type="button"
                >
                  <span className="flex items-start justify-between gap-3">
                    <span className="text-sm font-semibold leading-5 text-foreground">
                      {listing.title}
                    </span>
                    <Badge className="shrink-0" tone="neutral">
                      {listing.platform}
                    </Badge>
                  </span>
                  <span className="mt-1 flex items-center justify-between gap-3">
                    <span className="text-xs text-muted">
                      {[listing.company, listing.location]
                        .filter(Boolean)
                        .join(" / ") || "Location not stated"}
                    </span>
                    {listing.remote === true && (
                      <Badge className="shrink-0" tone="success">
                        Remote
                      </Badge>
                    )}
                  </span>
                </button>
                <div className="flex flex-wrap items-center gap-4 px-4 pb-3.5">
                  <button
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary-strong disabled:opacity-60"
                    disabled={saved || savingKey === key}
                    onClick={() => onSave(listing)}
                    type="button"
                  >
                    {saved ? (
                      <BookmarkCheck aria-hidden="true" className="size-4" />
                    ) : (
                      <Bookmark aria-hidden="true" className="size-4" />
                    )}
                    {saved ? "Saved to my jobs" : "Save to my jobs"}
                  </button>
                  {listing.applicationUrl && (
                    <a
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary-strong"
                      href={listing.applicationUrl}
                      rel="noreferrer noopener"
                      target="_blank"
                    >
                      <ExternalLink aria-hidden="true" className="size-4" />
                      View on {listing.platform}
                    </a>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="border-t border-line px-5 py-3 text-xs text-muted">
        {listings.length === 0
          ? "Showing 0 jobs"
          : `Showing 1–${listings.length} of ${totalCount} job${
              totalCount === 1 ? "" : "s"
            }`}
      </p>
    </Card>
  );
}
