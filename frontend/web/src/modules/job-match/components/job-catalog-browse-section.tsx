"use client";

import { Search } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge, Button, EmptyState, Input } from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { browseJobCatalog, saveJobCatalogListing } from "../api/job-match-api";
import type { Job, JobCatalogListing } from "../api/types";

const PAGE_SIZE = 10;

/** Full-catalog free-text search, independent of the role filter above it. */
export function JobCatalogBrowseSection({
  onSaved,
}: {
  onSaved: (job: Job) => void;
}) {
  const [query, setQuery] = useState("");
  const [listings, setListings] = useState<JobCatalogListing[]>();
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [savingKey, setSavingKey] = useState<string>();
  const [busy, setBusy] = useState<"initial" | "more">();
  const [failure, setFailure] = useState<string>();
  const [searched, setSearched] = useState(false);

  async function runSearch(
    event: FormEvent<HTMLFormElement> | undefined,
    nextOffset: number,
  ) {
    event?.preventDefault();
    setBusy(nextOffset === 0 ? "initial" : "more");
    setFailure(undefined);
    setSearched(true);
    try {
      const page = await browseJobCatalog({
        limit: PAGE_SIZE,
        offset: nextOffset,
        q: query.trim(),
      });
      setListings((current) =>
        nextOffset === 0
          ? page.listings
          : [...(current ?? []), ...page.listings],
      );
      setOffset(page.nextOffset);
      setHasMore(page.hasMore);
    } catch (error) {
      setFailure(requestErrorMessage(error, "Job search failed."));
    } finally {
      setBusy(undefined);
    }
  }

  async function save(listing: JobCatalogListing) {
    const key = `${listing.platform}:${listing.externalId}`;
    setSavingKey(key);
    setFailure(undefined);
    try {
      const job = await saveJobCatalogListing(
        listing.platform,
        listing.externalId,
      );
      onSaved(job);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "This listing could not be saved."),
      );
    } finally {
      setSavingKey(undefined);
    }
  }

  return (
    <section
      aria-labelledby="job-browse-heading"
      className="rounded-lg border border-line bg-surface p-4 shadow-sm"
    >
      <div className="flex items-center gap-2">
        <Search aria-hidden="true" className="size-5 text-primary" />
        <h2
          className="text-lg font-black text-foreground"
          id="job-browse-heading"
        >
          Search all jobs
        </h2>
      </div>
      <p className="mt-1 text-sm text-muted">
        Search the full catalog of published listings, independent of the role
        filter above.
      </p>
      <form
        className="mt-4 flex gap-2"
        onSubmit={(event) => void runSearch(event, 0)}
      >
        <Input
          aria-label="Search all jobs by keyword"
          className="flex-1"
          maxLength={200}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by title, company, or keyword"
          type="search"
          value={query}
        />
        <Button loading={busy === "initial"} type="submit">
          Search
        </Button>
      </form>

      {failure && <p className="mt-3 text-sm text-danger-strong">{failure}</p>}

      {searched && listings && listings.length === 0 ? (
        <EmptyState
          className="mt-4"
          description="No listings matched that search."
          title="No results"
        />
      ) : (
        listings &&
        listings.length > 0 && (
          <>
            <ul className="mt-4 grid gap-3 md:grid-cols-2">
              {listings.map((listing) => {
                const key = `${listing.platform}:${listing.externalId}`;
                return (
                  <li
                    className="rounded-lg border border-line bg-surface-subtle p-3"
                    key={key}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-bold text-foreground">
                          {listing.title}
                        </p>
                        <p className="mt-0.5 text-xs text-muted">
                          {[listing.company, listing.location]
                            .filter(Boolean)
                            .join(" / ")}
                        </p>
                      </div>
                      <Badge tone="neutral">{listing.platform}</Badge>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <Button
                        loading={savingKey === key}
                        onClick={() => void save(listing)}
                        variant="secondary"
                      >
                        Save to my jobs
                      </Button>
                      {listing.applicationUrl && (
                        <a
                          className="text-xs font-bold text-primary underline"
                          href={listing.applicationUrl}
                          rel="noreferrer noopener"
                          target="_blank"
                        >
                          View on {listing.platform}
                        </a>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
            {hasMore && (
              <div className="mt-4">
                <Button
                  loading={busy === "more"}
                  onClick={() => void runSearch(undefined, offset)}
                  variant="secondary"
                >
                  Load more
                </Button>
              </div>
            )}
          </>
        )
      )}
    </section>
  );
}
