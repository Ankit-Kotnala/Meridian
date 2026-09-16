"use client";

import {
  Bookmark,
  BookmarkCheck,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

import { Badge, Button, Card, EmptyState, cn } from "@rezumi/ui";

import type { JobCatalogListing } from "../api/types";

import { humanizePlatform } from "./job-search-filters";
import { listingKey } from "./job-selection";

/** Middle column of the job search: the result list itself. */
export function JobListingResults({
  description,
  listings,
  onNextPage,
  onOpen,
  onPreviousPage,
  onSave,
  page,
  pageBusy,
  pageSize,
  savedKeys,
  savingKey,
  selectedKey,
  totalCount,
}: {
  description: string;
  listings: readonly JobCatalogListing[];
  onNextPage: () => void;
  onOpen: (listing: JobCatalogListing) => void;
  onPreviousPage: () => void;
  onSave: (listing: JobCatalogListing) => void;
  page: number;
  pageBusy: boolean;
  pageSize: number;
  savedKeys: ReadonlySet<string>;
  savingKey: string | undefined;
  selectedKey: string | undefined;
  totalCount: number;
}) {
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const rangeStart = totalCount === 0 ? 0 : page * pageSize + 1;
  const rangeEnd =
    totalCount === 0
      ? 0
      : Math.min(totalCount, page * pageSize + listings.length);
  const canGoPrevious = page > 0;
  const canGoNext = page + 1 < totalPages;

  return (
    <Card as="section" aria-labelledby="job-results-heading">
      <div className="px-5 pb-4 pt-5">
        <h2
          className="text-base font-semibold tracking-[-0.01em] text-foreground"
          id="job-results-heading"
        >
          Open jobs
        </h2>
        <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
      </div>

      {listings.length === 0 ? (
        <div className="px-5 pb-5">
          <EmptyState
            description="No listings matched these filters. Clear them to browse the catalog again."
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
                      {humanizePlatform(listing.platform)}
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
                      View on {humanizePlatform(listing.platform)}
                    </a>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <div className="border-t border-line px-5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted">
            {totalCount === 0
              ? "Showing 0 jobs"
              : `Showing ${rangeStart}–${rangeEnd} of ${totalCount} job${
                  totalCount === 1 ? "" : "s"
                }`}
          </p>
          {totalCount > 0 ? (
            <p className="text-xs text-muted">
              Page {page + 1} of {totalPages}
            </p>
          ) : null}
        </div>
        {totalCount > pageSize ? (
          <div className="mt-3 flex items-center justify-center gap-2">
            <Button
              disabled={!canGoPrevious || pageBusy}
              loading={pageBusy && canGoPrevious}
              onClick={onPreviousPage}
              variant="secondary"
            >
              <ChevronLeft aria-hidden="true" className="size-4" />
              Previous
            </Button>
            <Button
              disabled={!canGoNext || pageBusy}
              loading={pageBusy && canGoNext}
              onClick={onNextPage}
              variant="secondary"
            >
              Next
              <ChevronRight aria-hidden="true" className="size-4" />
            </Button>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
