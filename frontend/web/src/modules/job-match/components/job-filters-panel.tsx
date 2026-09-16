"use client";

import { Search } from "lucide-react";
import type { FormEvent } from "react";

import { Button, Card, Select } from "@rezumi/ui";

import {
  humanizePlatform,
  seniorityOptions,
  workModelOptions,
  type JobSearchFilters,
  type SeniorityFilter,
  type WorkModelFilter,
} from "./job-search-filters";

/** Left rail of the job search: narrows the result list beside it. */
export function JobFiltersPanel({
  busy,
  filters,
  locations,
  onApply,
  onChange,
  onClear,
  platforms,
}: {
  busy: boolean;
  filters: JobSearchFilters;
  locations: readonly string[];
  onApply: () => void;
  onChange: (next: JobSearchFilters) => void;
  onClear: () => void;
  platforms: readonly string[];
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onApply();
  }

  return (
    <Card as="section" aria-labelledby="job-filters-heading">
      <form className="p-5" onSubmit={submit}>
        <h2
          className="text-base font-semibold tracking-[-0.01em] text-foreground"
          id="job-filters-heading"
        >
          Filters
        </h2>

        <div className="relative mt-4">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
          />
          <input
            aria-label="Search by title, company, or keyword"
            className="min-h-11 w-full rounded-[var(--radius-control)] border border-line-strong bg-surface pl-9 pr-3.5 text-sm text-foreground shadow-sm outline-none placeholder:text-muted hover:border-primary/70 focus:border-primary focus:ring-3 focus:ring-primary-soft"
            maxLength={200}
            onChange={(event) =>
              onChange({ ...filters, keyword: event.target.value })
            }
            placeholder="Title, company, or keyword"
            type="search"
            value={filters.keyword}
          />
        </div>

        <div className="mt-5 space-y-4">
          <label className="block text-xs font-semibold text-muted-strong">
            Source
            <Select
              className="mt-1.5"
              onChange={(event) =>
                onChange({ ...filters, platform: event.target.value })
              }
              value={filters.platform}
            >
              <option value="">Any source</option>
              {platforms.map((platform) => (
                <option key={platform} value={platform}>
                  {humanizePlatform(platform)}
                </option>
              ))}
            </Select>
          </label>

          <label className="block text-xs font-semibold text-muted-strong">
            Seniority
            <Select
              className="mt-1.5"
              onChange={(event) =>
                onChange({
                  ...filters,
                  seniority: event.target.value as SeniorityFilter,
                })
              }
              value={filters.seniority}
            >
              {seniorityOptions.map((option) => (
                <option key={option.value || "any"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </label>

          <label className="block text-xs font-semibold text-muted-strong">
            Work model
            <Select
              className="mt-1.5"
              onChange={(event) =>
                onChange({
                  ...filters,
                  workModel: event.target.value as WorkModelFilter,
                })
              }
              value={filters.workModel}
            >
              {workModelOptions.map((option) => (
                <option key={option.value || "any"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </label>

          <label className="block text-xs font-semibold text-muted-strong">
            Location
            <input
              aria-label="Filter by city, state, or region"
              className="mt-1.5 min-h-11 w-full rounded-[var(--radius-control)] border border-line-strong bg-surface px-3.5 text-sm text-foreground shadow-sm outline-none placeholder:text-muted hover:border-primary/70 focus:border-primary focus:ring-3 focus:ring-primary-soft"
              list="job-search-location-suggestions"
              maxLength={120}
              onChange={(event) =>
                onChange({ ...filters, location: event.target.value })
              }
              placeholder="City, state, or region"
              type="search"
              value={filters.location}
            />
            {locations.length > 0 ? (
              <datalist id="job-search-location-suggestions">
                {locations.map((location) => (
                  <option key={location} value={location} />
                ))}
              </datalist>
            ) : null}
          </label>
        </div>

        <Button className="mt-6 w-full" loading={busy} type="submit">
          Apply filters
        </Button>
        <Button
          className="mt-2 w-full"
          disabled={busy}
          onClick={onClear}
          variant="ghost"
        >
          Clear all
        </Button>
      </form>
    </Card>
  );
}
